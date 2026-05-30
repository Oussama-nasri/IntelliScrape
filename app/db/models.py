"""
SQLAlchemy models for the APII scraper project.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, UniqueConstraint
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Company(Base):
    __tablename__ = "companies"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(512), nullable=False)
    activity      = Column(String(512))
    governorate   = Column(String(128))
    phone         = Column(String(64))

    # LinkedIn enrichment
    linkedin_url  = Column(String(1024))
    website       = Column(String(1024))
    description   = Column(Text)
    size          = Column(String(128))
    sector        = Column(String(256))
    headquarters  = Column(String(256))
    company_type  = Column(String(128))
    founded       = Column(String(32))

    # Metadata
    source        = Column(String(64), default="apii_industrial")   # apii_industrial | apii_services
    scrape_stage  = Column(String(32), default="scraped")           # scraped | linkedin_found | linkedin_enriched
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("name", "governorate", name="uq_company_name_gov"),
    )

    def to_dict(self):
        return {
            "id":           self.id,
            "name":         self.name,
            "activity":     self.activity,
            "governorate":  self.governorate,
            "phone":        self.phone,
            "linkedin_url": self.linkedin_url,
            "website":      self.website,
            "description":  self.description,
            "size":         self.size,
            "sector":       self.sector,
            "headquarters": self.headquarters,
            "company_type": self.company_type,
            "founded":      self.founded,
            "source":       self.source,
            "scrape_stage": self.scrape_stage,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
            "updated_at":   self.updated_at.isoformat() if self.updated_at else None,
        }