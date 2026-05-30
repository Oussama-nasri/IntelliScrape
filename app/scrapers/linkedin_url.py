"""
LinkedIn URL finder using DuckDuckGo.
Pulls companies from DB (stage='scraped'), finds LinkedIn URLs, updates DB.
"""

import asyncio
import random
import re
from urllib.parse import parse_qs, urlparse, urlunparse

from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

from app.db.models import Company

DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/?q={query}&kl=us-en"
NAV_TIMEOUT = 30_000

_ua = UserAgent()


# ── URL utils ──────────────────────────────────────────────────────────────────

def random_ua() -> str:
    try:
        return _ua.chrome
    except Exception:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )


def sanitise_url(raw: str) -> str | None:
    try:
        p = urlparse(raw)
    except Exception:
        return None

    qs = parse_qs(p.query)
    if qs.get("uddg"):
        return sanitise_url(qs["uddg"][0])

    clean = urlunparse((p.scheme, p.netloc, p.path.rstrip("/"), "", "", ""))
    return clean or None


def is_linkedin_company(url: str) -> bool:
    return "linkedin.com/company/" in url


def force_french_linkedin(url: str) -> str:
    """Normalise any LinkedIn subdomain to fr.linkedin.com."""
    if not url or not isinstance(url, str):
        return url
    pattern = r"^https?://([a-z]{2,3}|www)(\.linkedin\.com/.*)"
    if re.match(pattern, url):
        return re.sub(pattern, r"https://fr\2", url)
    return url


def extract_linkedin_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found = set()
    for a in soup.find_all("a", href=True):
        clean = sanitise_url(a["href"])
        if clean and is_linkedin_company(clean):
            found.add(clean)
    return sorted(found)


# ── Core async search ──────────────────────────────────────────────────────────

async def _find_linkedin_url(page, company_name: str) -> str | None:
    query = f"{company_name} site:linkedin.com/company"
    url = DUCKDUCKGO_URL.format(query=query)
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        await asyncio.sleep(random.uniform(1.5, 3.0))
        html = await page.content()
        urls = extract_linkedin_urls(html)
        if urls:
            return force_french_linkedin(urls[0])
    except Exception as e:
        print(f"  [linkedin_url] Search error for '{company_name}': {e}")
    return None


# ── Public entry point ─────────────────────────────────────────────────────────

async def find_linkedin_urls_async(db: Session) -> dict:
    """
    Fetches all companies at stage='scraped' from the DB,
    searches DuckDuckGo for their LinkedIn URL,
    and updates the DB (stage → 'linkedin_found').

    Returns a summary dict.
    """
    companies = (
        db.query(Company)
        .filter(Company.scrape_stage == "scraped")
        .all()
    )

    if not companies:
        return {"processed": 0, "found": 0, "not_found": 0}

    print(f"[linkedin_url] {len(companies)} companies to process…")

    found_count = 0
    not_found_count = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(user_agent=random_ua(), locale="fr-FR")
        page = await context.new_page()

        try:
            for i, company in enumerate(companies, 1):
                print(f"  [{i}/{len(companies)}] {company.name}")

                linkedin_url = await _find_linkedin_url(page, company.name)

                if linkedin_url:
                    company.linkedin_url = linkedin_url
                    company.scrape_stage = "linkedin_found"
                    found_count += 1
                    print(f"    → {linkedin_url}")
                else:
                    company.scrape_stage = "linkedin_found"   # mark as attempted
                    not_found_count += 1
                    print("    → not found")

                db.commit()
                await asyncio.sleep(random.uniform(2, 4))

        finally:
            await context.close()
            await browser.close()

    print(f"[linkedin_url] Done. Found: {found_count} / Not found: {not_found_count}")
    return {
        "processed": len(companies),
        "found": found_count,
        "not_found": not_found_count,
    }


def find_linkedin_urls(db: Session) -> dict:
    """Sync wrapper so FastAPI background tasks can call this easily."""
    return asyncio.run(find_linkedin_urls_async(db))