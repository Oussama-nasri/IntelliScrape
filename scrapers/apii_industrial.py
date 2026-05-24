import time
import requests
from config import APII_INDUSTRIAL_URL, INDUSTRIAL_SECTORS, MIN_EMPLOYEES, HEADERS
from parsers.html_parser import parse_company_table, get_total_pages


# ── Form payload template ──────────────────────────────────────────────────────
def build_payload(secteur: str = "08") -> dict:
    """Builds the static form criteria for the POST body with a parameterizable sector."""
    payload = {
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
    return payload


def scrape_industrial(secteur: str = "08") -> list[dict]:
    """Full scrape of the APII Industrial directory for a specific sector.

    Returns a list of company dicts.
    """
    all_companies: list[dict] = []
    session = requests.Session()
    session.headers.update(HEADERS)

    print(f"[industrial] Starting APII Industrial scrape for sector: {secteur}…")

    # Generate the base search form criteria once for the specific sector
    payload = build_payload(secteur=secteur)

    # ── Page 1 — also detects total page count ─────────────────────────────
    # Send pagination via query string parameters (params)
    params = {"action": "search", "pagenum": 1}

    try:
        resp = session.post(
            APII_INDUSTRIAL_URL, data=payload, params=params, timeout=30
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [industrial] ERROR on sector {secteur}, page 1: {e}")
        return all_companies

    total_pages = get_total_pages(resp.text)
    companies = parse_company_table(resp.text)
    all_companies.extend(companies)
    print(f"  [industrial] Sector {secteur} | Page 1/{total_pages} → {len(companies)} companies")

    # ── Remaining pages ────────────────────────────────────────────────────
    for page in range(2, total_pages + 1):
        time.sleep(1.5)  # polite delay — don't hammer the server

        # Dynamically update the target page number in the URL parameters
        params = {"action": "search", "pagenum": page}

        try:
            resp = session.post(
                APII_INDUSTRIAL_URL, data=payload, params=params, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [industrial] ERROR on sector {secteur}, page {page}: {e}")
            continue

        companies = parse_company_table(resp.text)
        all_companies.extend(companies)
        print(
            f"  [industrial] Sector {secteur} | Page {page}/{total_pages} → {len(companies)} companies"
        )

    print(f"[industrial] Sector {secteur} done. Total: {len(all_companies)} companies collected.")
    return all_companies


def scrap_industrial_all() -> list[dict]:
    """Loops through all sectors defined in INDUSTRIAL_SECTORS,
    scrapes each one, and aggregates the results into a single list.
    """
    master_company_list: list[dict] = []

    print("[industrial_all] Starting global scrape for all sectors...")

    # Defensive check: if INDUSTRIAL_SECTORS is a dict (e.g., {"08": "Textile"}),
    # we want the keys. If it's a list or set, we loop directly.
    sectors_to_scrape = (
        INDUSTRIAL_SECTORS.keys()
        if isinstance(INDUSTRIAL_SECTORS, dict)
        else INDUSTRIAL_SECTORS
    )

    for secteur in sectors_to_scrape:
        # Cast to string just in case the configuration defines them as integers
        secteur_str = str(secteur)

        print(f"\n--- Scraping Sector Code: {secteur_str} ---")
        sector_companies = scrape_industrial(secteur=secteur_str)
        master_company_list.extend(sector_companies)

        # Polite delay between switching whole sectors to prevent IP blocks
        time.sleep(2.0)

    print(f"\n[industrial_all] Global scrape complete! Total aggregated companies: {len(master_company_list)}")
    return master_company_list