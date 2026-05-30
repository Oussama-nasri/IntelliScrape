import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Company
from app.scrapers.industrial import scrape_industrial, scrape_industrial_all
from app.scrapers.linkedin_url import find_linkedin_urls
from app.scrapers.linkedin_enrich import enrich_linkedin_profiles

from fastapi import File, UploadFile
import pandas as pd
import io

router = APIRouter(prefix="/scrape", tags=["Scraping"])

# Simple in-memory job tracker (good enough for a single-instance deploy)
_jobs: dict[str, dict] = {}
_executor = ThreadPoolExecutor(max_workers=2)


def _job_wrapper(job_id: str, fn, *args, **kwargs):
    _jobs[job_id]["status"] = "running"
    try:
        result = fn(*args, **kwargs)
        _jobs[job_id].update({"status": "done", "result": result})
    except Exception as e:
        _jobs[job_id].update({"status": "error", "error": str(e)})


def _start_job(name: str, fn, *args, **kwargs) -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"id": job_id, "name": name, "status": "queued", "result": None}
    _executor.submit(_job_wrapper, job_id, fn, *args, **kwargs)
    return job_id


# ── Job status ─────────────────────────────────────────────────────────────────

@router.get("/jobs", summary="List all scraping jobs")
def list_jobs():
    return list(_jobs.values())


@router.get("/jobs/{job_id}", summary="Get status of a specific job")
def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ── Stage 1 — APII Industrial ─────────────────────────────────────────────────

@router.post("/industrial", summary="Scrape APII Industrial directory")
def trigger_industrial(
    sector: Optional[str] = Query(None, description="Single sector code e.g. '08'. Omit to scrape all."),
    export_csv: bool = Query(True, description="Also export a CSV to /output"),
    db: Session = Depends(get_db),
):
    """
    Starts a scrape of the APII Industrial directory.

    - With `sector`: scrapes only that one sector code.
    - Without `sector`: scrapes all sectors defined in config.
    """
    from app.db.session import SessionLocal

    def _run():
        # Each background job needs its own DB session
        _db = SessionLocal()
        try:
            if sector:
                return scrape_industrial(secteur=sector, db=_db)
            else:
                return scrape_industrial_all(db=_db, export_csv=export_csv)
        finally:
            _db.close()

    job_name = f"industrial_sector_{sector}" if sector else "industrial_all"
    job_id = _start_job(job_name, _run)
    return {"job_id": job_id, "status": "queued", "message": "Scraping started in background"}


# ── Stage 2 — LinkedIn URL finder ─────────────────────────────────────────────

@router.post("/linkedin-urls", summary="Find LinkedIn URLs for scraped companies")
def trigger_linkedin_urls():
    """
    Queries the DB for all companies with stage='scraped',
    searches DuckDuckGo for each, and saves the LinkedIn URL.
    """
    from app.db.session import SessionLocal

    def _run():
        _db = SessionLocal()
        try:
            return find_linkedin_urls(_db)
        finally:
            _db.close()

    job_id = _start_job("linkedin_url_finder", _run)
    return {"job_id": job_id, "status": "queued", "message": "LinkedIn URL search started"}


# ── Stage 3 — LinkedIn enrichment ─────────────────────────────────────────────

@router.post("/linkedin-enrich", summary="Enrich companies from their LinkedIn pages")
def trigger_linkedin_enrich():
    """
    Queries the DB for all companies with stage='linkedin_found',
    scrapes their LinkedIn About page, and saves the enriched data.
    """
    from app.db.session import SessionLocal

    def _run():
        _db = SessionLocal()
        try:
            return enrich_linkedin_profiles(_db)
        finally:
            _db.close()

    job_id = _start_job("linkedin_enrich", _run)
    return {"job_id": job_id, "status": "queued", "message": "LinkedIn enrichment started"}


# ── Full pipeline ─────────────────────────────────────────────────────────────

@router.post("/pipeline", summary="Run the full scraping pipeline (stages 1→2→3)")
def trigger_pipeline(
    sector: Optional[str] = Query(None, description="Optional single sector to limit stage 1"),
    export_csv: bool = Query(True),
):
    """
    Runs all three stages sequentially in a single background job:
    1. APII Industrial scrape
    2. LinkedIn URL finder
    3. LinkedIn profile enrichment
    """
    from app.db.session import SessionLocal

    def _run():
        _db = SessionLocal()
        try:
            print("[pipeline] Stage 1 — APII Industrial…")
            if sector:
                scrape_industrial(secteur=sector, db=_db)
            else:
                scrape_industrial_all(db=_db, export_csv=export_csv)

            print("[pipeline] Stage 2 — LinkedIn URL finder…")
            url_result = find_linkedin_urls(_db)

            print("[pipeline] Stage 3 — LinkedIn enrichment…")
            enrich_result = enrich_linkedin_profiles(_db)

            return {
                "linkedin_urls": url_result,
                "linkedin_enrich": enrich_result,
            }
        finally:
            _db.close()

    job_id = _start_job("full_pipeline", _run)
    return {"job_id": job_id, "status": "queued", "message": "Full pipeline started"}


@router.post("/upload-csv", summary="Load a CSV file into the database")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a CSV file and upsert its rows into the companies table.
    Accepts any CSV that has at least a 'name' column.
    All other recognised columns (activity, governorate, phone,
    linkedin_url, website, description, size, sector, headquarters,
    company_type, founded) are mapped automatically if present.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents), dtype=str).fillna("")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse CSV: {e}")

    if "name" not in df.columns:
        raise HTTPException(status_code=422, detail="CSV must contain a 'name' column")

    COLUMN_MAP = {
        "name": "name", "activity": "activity", "governorate": "governorate",
        "phone": "phone", "linkedin_url": "linkedin_url", "website": "website",
        "description": "description", "size": "size", "sector": "sector",
        "headquarters": "headquarters", "company_type": "company_type",
        "type": "company_type",   # accept 'type' as alias
        "founded": "founded",
    }

    inserted = 0
    updated  = 0
    skipped  = 0

    seen = set()

    for _, row in df.iterrows():
        name = row.get("name", "").strip()
        if not name:
            skipped += 1
            continue

        values = {db_col: row[csv_col].strip()
                  for csv_col, db_col in COLUMN_MAP.items()
                  if csv_col in df.columns and row.get(csv_col, "").strip()}

        gov = values.get("governorate", "")
        dedup_key = (name, gov)
        if dedup_key in seen:
            skipped += 1
            continue
        seen.add(dedup_key)

        if values.get("website") or values.get("description"):
            values["scrape_stage"] = "linkedin_enriched"
        elif values.get("linkedin_url"):
            values["scrape_stage"] = "linkedin_found"
        else:
            values["scrape_stage"] = "scraped"

        values["source"] = "csv_import"

        try:
            existing = db.query(Company).filter_by(name=name, governorate=gov).first()
            if existing:
                for k, v in values.items():
                    if v:
                        setattr(existing, k, v)
                updated += 1
            else:
                db.add(Company(**values))
                db.flush()  # catch constraint errors per-row, not at the end
                inserted += 1
        except Exception:
            db.rollback()  # roll back just this row, keep going
            skipped += 1

    db.commit()

    return {
        "filename": file.filename,
        "rows_read": len(df),
        "inserted": inserted,
        "updated":  updated,
        "skipped":  skipped,
    }