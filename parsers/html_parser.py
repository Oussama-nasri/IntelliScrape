# parsers/html_parser.py
"""
Parses the paginated HTML tables returned by the APII POST responses.
Both dbi.asp (industrial) and dbS.asp (services) return the same table format.
"""

from bs4 import BeautifulSoup
import re

def parse_company_table(html: str) -> list[dict]:
    """
    Extract all company rows from an APII results page.

    Returns a list of dicts, one per company:
        {
            "name":       str,
            "activity":   str,
            "governorate": str,
            "phone":      str,   # may be empty
        }
    """
    soup = BeautifulSoup(html, "lxml")
    companies = []

    # APII tables use a class like "tableau" or are the main data table —
    # we grab every <tr> that has 4–6 <td> children (data rows, not headers).
    tables = soup.find_all("table")
    if not tables:
        return companies

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue  # skip header rows / empty rows

            # Defensive extraction — strip whitespace, collapse inner newlines
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

            # Skip rows that look like column headers
            if company["name"].lower() in ("raison sociale", "société", "nom", "","Dénomination"):
                continue

            companies.append(company)

    return companies


def get_total_pages(html: str) -> int:
    """Try to detect how many result pages exist.

    Supports "Page X sur Y" or "Page X de Y" configurations.
    Returns 1 if pagination cannot be detected.
    """
    soup = BeautifulSoup(html, "lxml")

    # 1. Flatten the text into a single string, inserting spaces between tags
    full_text = soup.get_text(separator=" ", strip=True)

    # 2. Use regex to find "page <number> de/sur <total_pages>"
    # \s+ matches any whitespace
    # (?:de|sur) matches either "de" or "sur"
    # (\d+) captures the target total page number
    match = re.search(r"page\s+\d+\s+(?:de|sur)\s+(\d+)", full_text, re.IGNORECASE)

    if match:
        return int(match.group(1))

    # Fallback: count pagination links
    pagination_links = soup.select("a[href*='page='], a[href*='Page=']")
    if pagination_links:
        page_nums = []
        for link in pagination_links:
            href = link.get("href", "")
            # Using regex here makes URL parameter extraction safer too
            url_match = re.search(r"[Pp]age=(\d+)", href)
            if url_match:
                page_nums.append(int(url_match.group(1)))
        if page_nums:
            return max(page_nums)

    return 1
