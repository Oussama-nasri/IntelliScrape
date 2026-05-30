"""
APII Industrial directory scraper.
Saves results to MySQL and optionally exports a CSV.
"""

import time
import requests
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.config import APII_INDUSTRIAL_URL, INDUSTRIAL_SECTORS, HEADERS, INDUSTRIAL_CSV
from app.parsers.html_parser import parse_company_table, get_total_pages
from app.db.models import Company


# ── Payload builder ────────────────────────────────────────────────────────────

def build_payload(secteur: str = "01") -> dict:
    return {
        "secteur": secteur,
        "branche": "",
        "produit": "",
        "Denomination": "",
        "District": "",
        "Gouvernorat": "",
        "delegation": "",
        "pays": "",
        "regime": "",
        "sex": "",
        "ent_prd": "",
        "cap1": "",
        "cap2": "",
        "emp1": "",
        "emp2": "",
        "action": "search",
    }


# ── Single sector scrape ───────────────────────────────────────────────────────

def scrape_industrial(
    secteur: str = "01",
    db: Session | None = None,
) -> list[dict]:
    """
    Scrapes all pages for one sector.
    If `db` is provided, upserts each page's results immediately.
    Returns a flat list of company dicts.
    """
    all_companies: list[dict] = []
    session = requests.Session()
    session.headers.update(HEADERS)

    print(f"[industrial] Sector {secteur} — starting…")

    payload = build_payload(secteur=secteur)
    params = {"action": "search", "pagenum": 1}

    try:
        resp = session.post(APII_INDUSTRIAL_URL, data=payload, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [industrial] ERROR sector {secteur}, page 1: {e}")
        return all_companies

    total_pages = get_total_pages(resp.text)
    companies = parse_company_table(resp.text)
    all_companies.extend(companies)
    print(f"  [industrial] Sector {secteur} | 1/{total_pages} → {len(companies)} companies")

    if db:
        _upsert_companies(db, companies, source="apii_industrial")

    for page in range(2, total_pages + 1):
        time.sleep(1.5)
        params = {"action": "search", "pagenum": page}
        try:
            resp = session.post(APII_INDUSTRIAL_URL, data=payload, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [industrial] ERROR sector {secteur}, page {page}: {e}")
            continue

        companies = parse_company_table(resp.text)
        all_companies.extend(companies)
        print(f"  [industrial] Sector {secteur} | {page}/{total_pages} → {len(companies)} companies")

        if db:
            _upsert_companies(db, companies, source="apii_industrial")

    print(f"[industrial] Sector {secteur} done. Total: {len(all_companies)}")
    return all_companies


# ── All sectors ────────────────────────────────────────────────────────────────

def scrape_industrial_all(
    db: Session | None = None,
    export_csv: bool = True,
) -> list[dict]:
    """
    Loops through all sectors in config.INDUSTRIAL_SECTORS.
    Saves to DB when `db` is provided.
    Exports a CSV when `export_csv` is True.
    """
    master: list[dict] = []

    sectors = (
        INDUSTRIAL_SECTORS.keys()
        if isinstance(INDUSTRIAL_SECTORS, dict)
        else INDUSTRIAL_SECTORS
    )

    for secteur in sectors:
        s = str(secteur)
        print(f"\n--- Scraping sector {s} ---")
        companies = scrape_industrial(secteur=s, db=db)
        master.extend(companies)
        time.sleep(2.0)

    print(f"\n[industrial_all] Done. Total: {len(master)} companies")

    if export_csv and master:
        _export_csv(master, INDUSTRIAL_CSV)

    return master


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _upsert_companies(db: Session, companies: list[dict], source: str) -> None:
    """
    Insert-or-ignore companies into the DB.
    On duplicate (name + governorate) we skip to preserve enriched data.
    """
    if not companies:
        return

    for c in companies:
        stmt = mysql_insert(Company).values(
            name=c.get("name", ""),
            activity=c.get("activity", ""),
            governorate=c.get("governorate", ""),
            phone=c.get("phone", ""),
            source=source,
            scrape_stage="scraped",
        )
        # On duplicate key — skip (don't overwrite enriched data)
        stmt = stmt.prefix_with("IGNORE")
        db.execute(stmt)

    db.commit()


# ── CSV export helper ──────────────────────────────────────────────────────────

def _export_csv(companies: list[dict], filepath: str) -> None:
    import os
    import pandas as pd

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    df = pd.DataFrame(companies)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"[industrial] CSV exported → {filepath}")