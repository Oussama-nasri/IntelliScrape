# app/parsers/html_parser.py
"""
Parses the paginated HTML tables returned by the APII POST responses.
"""

import re
from bs4 import BeautifulSoup


def parse_company_table(html: str) -> list[dict]:
    """
    Extract all company rows from an APII results page.

    Returns a list of dicts:
        { "name", "activity", "governorate", "phone" }
    """
    soup = BeautifulSoup(html, "lxml")
    companies = []

    tables = soup.find_all("table")
    if not tables:
        return companies

    SKIP_NAMES = {"raison sociale", "société", "nom", "", "dénomination"}

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            def cell_text(idx):
                if idx < len(cells):
                    return cells[idx].get_text(separator=" ", strip=True)
                return ""

            company = {
                "name":        cell_text(0),
                "activity":    cell_text(1),
                "governorate": cell_text(3),
                "phone":       cell_text(2),
            }

            if company["name"].lower() in SKIP_NAMES:
                continue

            companies.append(company)

    return companies


def get_total_pages(html: str) -> int:
    """Detect how many result pages exist. Returns 1 if not detectable."""
    soup = BeautifulSoup(html, "lxml")
    full_text = soup.get_text(separator=" ", strip=True)

    match = re.search(
        r"page\s+\d+\s+(?:de|sur)\s+(\d+)", full_text, re.IGNORECASE
    )
    if match:
        return int(match.group(1))

    pagination_links = soup.select("a[href*='page='], a[href*='Page=']")
    if pagination_links:
        page_nums = []
        for link in pagination_links:
            href = link.get("href", "")
            url_match = re.search(r"[Pp]age=(\d+)", href)
            if url_match:
                page_nums.append(int(url_match.group(1)))
        if page_nums:
            return max(page_nums)

    return 1