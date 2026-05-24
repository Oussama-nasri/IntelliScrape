# scrapers/rne_enrichment.py
"""
RNE Enrichment — feeds company names from the APII CSV into the RNE portal
and extracts verified legal data: legal status, capital, creation date,
headquarters address, and managing directors.

The RNE portal is a JavaScript Single-Page Application, so Selenium is
required (unlike the APII sites which are plain POST forms).

Requirements:
  - Google Chrome installed
  - `pip install selenium webdriver-manager`
"""

import time
import csv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

from config import RNE_URL, INDUSTRIAL_CSV, ENRICHED_CSV
from exporters.csv_exporter import save_to_csv


# ── Browser setup ──────────────────────────────────────────────────────────────
def create_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--lang=fr")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


# ── RNE search for a single company ───────────────────────────────────────────
def search_rne(driver: webdriver.Chrome, company_name: str) -> dict:
    """
    Searches the RNE portal for `company_name`.
    Returns a dict with enrichment fields (empty strings if not found).
    """
    result = {
        "name":             company_name,
        "rne_legal_status": "",
        "rne_capital":      "",
        "rne_created":      "",
        "rne_address":      "",
        "rne_directors":    "",
    }

    try:
        driver.get(RNE_URL)
        wait = WebDriverWait(driver, 15)

        # Wait for the search input to appear (class/id may vary — inspect the SPA)
        search_input = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='search'], input[placeholder*='Recherche'], input[placeholder*='search']"))
        )
        search_input.clear()
        search_input.send_keys(company_name)
        search_input.send_keys(Keys.RETURN)

        time.sleep(2)  # Let the SPA fetch and render results

        # Click the first result row
        first_result = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "table tbody tr:first-child, .result-row:first-child"))
        )
        first_result.click()
        time.sleep(2)

        # Extract fields — selectors depend on the RNE portal's HTML structure.
        # Inspect the portal manually and update these CSS selectors.
        def safe_get(selector: str) -> str:
            try:
                el = driver.find_element(By.CSS_SELECTOR, selector)
                return el.text.strip()
            except Exception:
                return ""

        result["rne_legal_status"] = safe_get(".legal-form, [data-field='formeJuridique']")
        result["rne_capital"]      = safe_get(".capital, [data-field='capital']")
        result["rne_created"]      = safe_get(".creation-date, [data-field='dateCreation']")
        result["rne_address"]      = safe_get(".address, [data-field='adresse']")
        result["rne_directors"]    = safe_get(".directors, [data-field='gerants']")

    except Exception as e:
        print(f"    [rne] Could not enrich '{company_name}': {e}")

    return result


# ── Batch enrichment ───────────────────────────────────────────────────────────
def enrich_from_csv(input_csv: str = INDUSTRIAL_CSV,
                    output_csv: str = ENRICHED_CSV,
                    headless: bool = True,
                    limit: int = None) -> None:
    """
    Reads company names from `input_csv`, enriches each via RNE,
    and saves results to `output_csv`.

    Args:
        input_csv:  Path to the APII-scraped CSV.
        output_csv: Path for the enriched output CSV.
        headless:   Run Chrome without a visible window.
        limit:      Cap the number of companies to process (None = all).
    """
    if not os.path.exists(input_csv):
        print(f"[rne] Input CSV not found: {input_csv}")
        return

    # Load company names from the input CSV
    with open(input_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        companies = [row["name"] for row in reader if row.get("name")]

    if limit:
        companies = companies[:limit]

    print(f"[rne] Enriching {len(companies)} companies from {input_csv}…")

    driver = create_driver(headless=headless)
    enriched = []

    try:
        for i, name in enumerate(companies, 1):
            print(f"  [rne] {i}/{len(companies)}: {name}")
            data = search_rne(driver, name)
            enriched.append(data)
            time.sleep(1.5)  # Polite delay between requests
    finally:
        driver.quit()

    save_to_csv(enriched, output_csv)
    print(f"[rne] Enrichment complete → {output_csv}")
