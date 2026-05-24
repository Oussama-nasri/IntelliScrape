# 🏭 IntelliScrape — B2B Industrial Intelligence Platform

> **Turn public directories into a live pipeline of qualified prospects — automatically.**

---

## What This Is

IntelliScrape is a modular B2B lead intelligence system built for companies that need to **identify, qualify, and reach out to industrial and service firms** across multiple countries and directories. It aggregates data from government industrial registries, national business registers, professional networks, and sector-specific portals — then serves that data through a clean **FastAPI layer** ready for direct consumption by sales teams, CRMs, or AI agents.

The immediate use case: a company seeking **robotics, automation, or hardware integration partners** in Tunisia needed a reliable way to discover which factories, electronics firms, and maintenance companies were large enough to afford modern systems — and to get their verified contact information before competitors did. This tool was built to solve exactly that problem.

---

## The Business Case

Cold outreach fails when it's untargeted. The average sales team wastes 60–70% of prospecting time on companies that are too small, in the wrong sector, or already locked into a competitor. IntelliScrape solves this by delivering a **pre-filtered, verified, enriched list** of companies that match your exact criteria — sector, size, location, legal status — before you make a single call.

**Who benefits:**

- **Business Development teams** prospecting for integration partners, distributors, or clients in a new market
- **Consultancies** mapping the industrial landscape of a country before engaging a client
- **Investors** doing sector due diligence on a region's manufacturing base
- **AI-powered sales agents** that need structured company data to personalize outreach at scale

---

## Project Structure

```
scraping/
├── apii_industrial.py       # APII government industrial directory scraper
├── linkedin_scraper.py      # LinkedIn company page enrichment
├── rne_enrichment.py        # RNE legal registry enrichment (Selenium)
├── ween_scraper.py          # Ween.tn B2B portal scraper
│
├── apii_industrial.csv      # Output: scraped + enriched company records
│
└── api/                     # FastAPI layer
    └── main.py              # REST endpoints for all scraped data
```

---

## Data Sources

### 1. `apii_industrial.py` — APII Industrial Directory
**Source:** [tunisieindustrie.nat.tn/fr/dbi.asp](https://www.tunisieindustrie.nat.tn/fr/dbi.asp)

The Agence de Promotion de l'Industrie et de l'Innovation (APII) maintains Tunisia's most authoritative directory of registered industrial companies. This scraper sends POST requests replicating the browser's form submission, iterates through all paginated result pages, and extracts structured company records.

**Filters applied:**
- `IMM` — Industries mécaniques et métallurgiques *(robotics, machining, metal fabrication)*
- `IEE` — Industries électriques, électroniques et de l'électroménager *(PCB, sensors, automation)*
- Minimum 10 employees *(filters out artisan micro-shops)*

**Fields extracted:** Company name · Activity description · Governorate · Phone · Email

---

### 2. `rne_enrichment.py` — RNE Legal Registry
**Source:** [registre-entreprises.tn](https://registre-entreprises.tn/rne-public#/)

The Registre National des Entreprises is the official Tunisian legal business registry. Because it's a JavaScript SPA, this module uses Selenium to feed company names from the APII output and extract their verified legal profiles.

**Fields added:** Legal form (SARL/SA/etc.) · Registered capital · Date of incorporation · Official HQ address · Managing directors / partners

This is the **trust layer** — it transforms a marketing directory entry into a legally verified entity you can confidently include in a proposal or due diligence report.

---

### 3. `linkedin_scraper.py` — LinkedIn Company Pages
**Source:** LinkedIn public company profiles

Enriches records with professional presence data — company size range, industry tags, description, follower count, and recent activity. Useful for gauging a company's digital maturity and whether they're actively hiring technical roles (a signal of growth).

---

### 4. `ween_scraper.py` — Ween.tn B2B Portal
**Source:** [ween.tn](https://www.ween.tn)

Ween is a Tunisian B2B marketplace listing suppliers, manufacturers, and service providers. It often contains companies not listed in APII (newer firms, informal sector players who have gone digital). This scraper captures additional leads that cross-reference well with the APII dataset.

---

## FastAPI Endpoints

The scraping pipeline feeds a FastAPI server that exposes the data as structured REST endpoints — making it trivially easy to integrate with a CRM, a sales dashboard, or an AI agent.

```
GET  /companies                   # Full list with filters (sector, governorate, size)
GET  /companies/{id}              # Single company profile (all enriched fields)
GET  /companies/search?q=...      # Fuzzy name search
GET  /companies/export/csv        # Download current dataset as CSV
POST /scrape/trigger              # Kick off a new scraping run
GET  /scrape/status               # Check if a scraping job is running
```

Example query:

```bash
curl "http://localhost:8000/companies?sector=IMM&min_employees=50&governorate=Tunis"
```

Returns a paginated JSON array of enriched company records ready for your pipeline.

---

## Multi-Country & Multi-Industry Extensibility

IntelliScrape was designed with a **plug-and-play scraper architecture**. Adding a new country or sector is as simple as adding a new scraper module that outputs the same CSV schema. The FastAPI layer and enrichment pipeline remain unchanged.

**Countries already mappable with equivalent government sources:**

| Country | Industrial Registry | Legal Registry |
|---------|---------------------|----------------|
| Tunisia | APII (dbi.asp) | RNE |
| Morocco | AMICA / CRI portals | RC Maroc |
| Algeria | Chambre de Commerce et d'Industrie | CNRC |
| Egypt | Industrial Development Authority | Commercial Register |
| France | Annuaire des Entreprises | INSEE / Infogreffe |
| Germany | IHK Unternehmensregister | Handelsregister |

**Industries supported out of the box (via sector code config):**

- Mechanical & Metallurgical (robotics targets, machining partners)
- Electrical & Electronics (PCB, sensors, integration)
- Chemicals & Plastics (process automation)
- Textiles & Clothing (industrial sewing automation)
- Agri-food (packaging line automation)
- Building materials (heavy machinery)
- Hardware installation & maintenance services

To target a new industry, update the `INDUSTRIAL_SECTORS` list in `config.py`. No code changes needed.

---

## MCP Tool — Plug Into an AI Agent

This project ships with an **MCP (Model Context Protocol) interface**, which means it can be used as a **tool inside any agentic AI system** — Claude, GPT, LangChain agents, AutoGen, or any framework that supports tool-calling.

Your AI agent can call:

```
tool: search_companies
args: { "sector": "IEE", "governorate": "Sfax", "min_employees": 20 }

tool: enrich_company
args: { "name": "Société Tunisienne de Mécatronique" }

tool: export_leads
args: { "format": "csv", "limit": 100 }
```

**What this unlocks:**

An AI sales agent can autonomously:
1. Search for companies matching the client's ideal customer profile
2. Enrich each company with legal and LinkedIn data
3. Draft a personalized cold outreach email per company using public context
4. Rank leads by likelihood of interest based on size, activity, and digital presence
5. Export a ready-to-dial call list to the CRM

No human in the loop required between "define your target market" and "here are 200 qualified, enriched leads with draft emails."

---

## Output: `apii_industrial.csv`

The main output file. Each row is a company record with all enrichment layers merged:

| Column | Source | Description |
|--------|--------|-------------|
| `name` | APII | Registered company name |
| `activity` | APII | Main declared business activity |
| `governorate` | APII | Region |
| `phone` | APII | Listed phone number |
| `email` | APII | Listed email |
| `rne_legal_status` | RNE | SARL, SA, GIE, etc. |
| `rne_capital` | RNE | Registered capital in TND |
| `rne_created` | RNE | Date of incorporation |
| `rne_address` | RNE | Official headquarters address |
| `rne_directors` | RNE | Names of managing directors |
| `linkedin_url` | LinkedIn | Company page URL |
| `linkedin_size` | LinkedIn | Employee range (e.g. 51–200) |
| `ween_url` | Ween | Ween.tn profile link |

---

## Quickstart

```bash
# Install dependencies
pip install -r requirements.txt

# Run APII scrape only (fast, no browser)
python apii_industrial.py

# Run full pipeline including RNE enrichment
python run.py

# Start the API server
uvicorn api.main:app --reload --port 8000

# View interactive API docs
open http://localhost:8000/docs
```

---

## Ethical & Legal Note

All data scraped by this tool is **publicly accessible** through official government portals and public business directories. No authentication is bypassed. Request delays are built in to avoid overloading servers. This tool is intended for **legitimate B2B prospecting and market research** purposes only. Always comply with the terms of service of any platform you query and with applicable data protection regulations (including Law No. 2004-63 on personal data protection in Tunisia).

---

*Built for speed. Designed for scale. Ready for your AI agent.*