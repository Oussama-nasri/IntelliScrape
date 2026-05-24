# config.py — Central configuration for all scrapers

# ── URLs ──────────────────────────────────────────────────────────────────────
APII_INDUSTRIAL_URL = "https://www.tunisieindustrie.nat.tn/fr/dbi.asp"
APII_SERVICES_URL   = "https://www.tunisieindustrie.nat.tn/fr/dbS.asp"
RNE_URL             = "https://registre-entreprises.tn/rne-public#/"

# ── Sector codes (from the APII form — captured via browser DevTools) ─────────
# These are the checkbox values sent in the POST payload.
# Add or remove codes to change which sectors are scraped.
INDUSTRIAL_SECTORS = [
    "01","02","03","04","05","06","07","08","09",
]

# ── Employee size filter ───────────────────────────────────────────────────────
# Mirrors the "Nombre d'employés" dropdown on the APII page.
# Options typically: "" (all), "10", "50", "100", "200"
MIN_EMPLOYEES = "10"

# ── HTTP headers — mimic a real browser to avoid 403s ─────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://www.tunisieindustrie.nat.tn/fr/dbi.asp",
}

# ── Output ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR = "output"

INDUSTRIAL_CSV  = f"{OUTPUT_DIR}/apii_industrial.csv"
SERVICES_CSV    = f"{OUTPUT_DIR}/apii_services.csv"
ENRICHED_CSV    = f"{OUTPUT_DIR}/enriched_rne.csv"
