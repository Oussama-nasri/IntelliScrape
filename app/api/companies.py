"""
/api/companies — query the database.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.db.session import get_db
from app.db.models import Company

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("", summary="List companies with filtering and pagination")
def list_companies(
    # Pagination
    page:  int = Query(1,   ge=1,   description="Page number"),
    limit: int = Query(50,  ge=1,  le=500, description="Results per page"),

    # Filters
    search:       Optional[str] = Query(None, description="Search name or activity"),
    governorate:  Optional[str] = Query(None),
    stage:        Optional[str] = Query(None, description="scraped | linkedin_found | linkedin_enriched"),
    source:       Optional[str] = Query(None, description="apii_industrial | apii_services"),
    has_linkedin: Optional[bool] = Query(None, description="Filter by whether linkedin_url exists"),

    db: Session = Depends(get_db),
):
    q = db.query(Company)

    if search:
        q = q.filter(
            or_(
                Company.name.ilike(f"%{search}%"),
                Company.activity.ilike(f"%{search}%"),
            )
        )
    if governorate:
        q = q.filter(Company.governorate.ilike(f"%{governorate}%"))
    if stage:
        q = q.filter(Company.scrape_stage == stage)
    if source:
        q = q.filter(Company.source == source)
    if has_linkedin is True:
        q = q.filter(Company.linkedin_url.isnot(None), Company.linkedin_url != "")
    elif has_linkedin is False:
        q = q.filter(or_(Company.linkedin_url.is_(None), Company.linkedin_url == ""))

    total = q.count()
    items = q.offset((page - 1) * limit).limit(limit).all()

    return {
        "total":    total,
        "page":     page,
        "limit":    limit,
        "pages":    (total + limit - 1) // limit,
        "items":    [c.to_dict() for c in items],
    }


@router.get("/stats", summary="Database statistics")
def stats(db: Session = Depends(get_db)):
    total         = db.query(func.count(Company.id)).scalar()
    by_stage      = (
        db.query(Company.scrape_stage, func.count(Company.id))
        .group_by(Company.scrape_stage)
        .all()
    )
    by_governorate = (
        db.query(Company.governorate, func.count(Company.id))
        .group_by(Company.governorate)
        .order_by(func.count(Company.id).desc())
        .limit(15)
        .all()
    )
    with_linkedin = (
        db.query(func.count(Company.id))
        .filter(Company.linkedin_url.isnot(None), Company.linkedin_url != "")
        .scalar()
    )

    return {
        "total_companies":   total,
        "with_linkedin_url": with_linkedin,
        "by_stage": {stage: count for stage, count in by_stage},
        "top_governorates": [
            {"governorate": g, "count": c} for g, c in by_governorate
        ],
    }


@router.get("/{company_id}", summary="Get a single company by ID")
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).get(company_id)
    if not company:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Company not found")
    return company.to_dict()