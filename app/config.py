import os

# ── URLs ──────────────────────────────────────────────────────────────────────
APII_INDUSTRIAL_URL = "https://www.tunisieindustrie.nat.tn/fr/dbi.asp"
APII_SERVICES_URL   = "https://www.tunisieindustrie.nat.tn/fr/dbS.asp"

# ── Sector codes ──────────────────────────────────────────────────────────────
INDUSTRIAL_SECTORS = [
    "01","02","03","04","05","06","07","08","09",
]

# ── Employee size filter ───────────────────────────────────────────────────────
MIN_EMPLOYEES = "10"

# ── HTTP headers ───────────────────────────────────────────────────────────────
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
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")

INDUSTRIAL_CSV  = f"{OUTPUT_DIR}/apii_industrial.csv"
SERVICES_CSV    = f"{OUTPUT_DIR}/apii_services.csv"

# ── Database ───────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "mysql+pymysql://scraper:scraper@db:3306/scraper_db"
)