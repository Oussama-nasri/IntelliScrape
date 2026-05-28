"""
CSV LinkedIn Company URL Finder (DuckDuckGo Version)
====================================================

This merges:

1. Your CSV/checkpoint/save logic
2. The DuckDuckGo Playwright scraper logic

No Apify dependency anymore.

Dependencies:
    pip install pandas playwright beautifulsoup4 fake-useragent python-dotenv
    playwright install chromium
"""

import asyncio
import json
import os
import random
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlunparse

import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fake_useragent import UserAgent
from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# ENV
# ---------------------------------------------------------------------------

load_dotenv()

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

CHECKPOINT_FILE = "search_checkpoint.json"
SAVE_EVERY = 5
NAV_TIMEOUT = 30000

DUCKDUCKGO_URL = (
    "https://html.duckduckgo.com/html/?q={query}&kl=us-en"
)

_ua = UserAgent()

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def random_ua() -> str:
    try:
        return _ua.chrome
    except Exception:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(mapping):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def sanitise_url(raw: str) -> str | None:
    try:
        p = urlparse(raw)
    except Exception:
        return None

    qs = parse_qs(p.query)

    # DuckDuckGo redirect format
    if qs.get("uddg"):
        return sanitise_url(qs["uddg"][0])

    clean = urlunparse(
        (p.scheme, p.netloc, p.path.rstrip("/"), "", "", "")
    )

    return clean or None


def is_linkedin_company(url: str) -> bool:
    return "linkedin.com/company/" in url


def extract_linkedin_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")

    found = set()

    for a in soup.find_all("a", href=True):
        clean = sanitise_url(a["href"])

        if clean and is_linkedin_company(clean):
            found.add(clean)

    return sorted(found)

# ---------------------------------------------------------------------------
# DUCKDUCKGO SEARCH
# ---------------------------------------------------------------------------

async def find_linkedin_url(page, company_name):
    query = f"{company_name} site:linkedin.com/company"
    url = DUCKDUCKGO_URL.format(query=query)

    try:
        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=NAV_TIMEOUT,
        )

        if response:
            print(f"HTTP Status: {response.status}")

        await asyncio.sleep(random.uniform(1.5, 3.0))

        html = await page.content()

        urls = extract_linkedin_urls(html)

        if urls:
            return urls[0]

    except Exception as e:
        print(f"  Search error: {e}")

    return None

# ---------------------------------------------------------------------------
# MAIN CSV PROCESSOR
# ---------------------------------------------------------------------------

async def find_and_save_linkedin_urls(
    input_csv,
    company_col,
    output_csv=None,
):
    if output_csv is None:
        output_csv = input_csv

    df = pd.read_csv(input_csv)

    if company_col not in df.columns:
        raise ValueError(
            f"Column '{company_col}' not found. "
            f"Available: {list(df.columns)}"
        )

    if "linkedin_url" not in df.columns:
        df["linkedin_url"] = None

    checkpoint = load_checkpoint()

    # Restore checkpoint values
    for i, row in df.iterrows():
        name = str(row[company_col]).strip()

        if name in checkpoint:
            df.at[i, "linkedin_url"] = checkpoint[name]

    pending = df[df["linkedin_url"].isna()].index.tolist()

    total = len(df)

    print(f"Total companies : {total}")
    print(f"Already done    : {total - len(pending)}")
    print(f"Remaining       : {len(pending)}\n")

    found_since_last_save = 0

    async with async_playwright() as pw:

        browser = await pw.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await browser.new_context(
            user_agent=random_ua(),
            locale="en-US",
        )

        page = await context.new_page()

        try:

            for count, i in enumerate(pending):

                name = str(df.at[i, company_col]).strip()

                print(
                    f"[{count + 1}/{len(pending)}] "
                    f"Searching: {name}"
                )

                url = await find_linkedin_url(page, name)

                df.at[i, "linkedin_url"] = (
                    url if url else "Not found"
                )

                checkpoint[name] = (
                    url if url else "Not found"
                )

                print(f"  → {url or 'Not found'}")

                save_checkpoint(checkpoint)

                found_since_last_save += 1

                # Save every N rows
                if found_since_last_save >= SAVE_EVERY:

                    df.to_csv(
                        output_csv,
                        index=False,
                        encoding="utf-8-sig",
                    )

                    print(f"  💾 CSV saved ({output_csv})")

                    found_since_last_save = 0

                await asyncio.sleep(
                    random.uniform(2, 4)
                )

        finally:
            await context.close()
            await browser.close()

    # Final save
    df.to_csv(
        output_csv,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\nDone. Results saved to {output_csv}")

    found = df[
        (df["linkedin_url"].notna())
        & (df["linkedin_url"] != "Not found")
    ]

    not_found = df[
        df["linkedin_url"] == "Not found"
    ]

    print(f"Found     : {len(found)}")
    print(f"Not found : {len(not_found)}")

    return df

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent

OUTPUT_DIR = SCRIPT_DIR.parent / "output"

input_file_path = OUTPUT_DIR / "apii_industrial_ALL.csv"

output_file_path = (
    OUTPUT_DIR / "apii_industrial_lkdn_ALL.csv"
)

# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    asyncio.run(
        find_and_save_linkedin_urls(
            input_csv=str(input_file_path),
            company_col="name",
            output_csv=str(output_file_path),
        )
    )