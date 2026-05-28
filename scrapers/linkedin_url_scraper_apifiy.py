import pandas as pd
from apify_client import ApifyClient
import time
import random
import json
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

APIFY_TOKEN     = os.getenv("APIFY_TOKEN")
CHECKPOINT_FILE = "search_checkpoint.json"
SAVE_EVERY      = 5

client = ApifyClient(APIFY_TOKEN)

# --- Checkpoint helpers ---

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_checkpoint(mapping):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

# --- Search ---

def find_linkedin_url(company_name):
    run_input = {
        "keyword":        f"{company_name} site:linkedin.com/company",
        "include_merged": True,
        "limit":          "10",
        "country":        "FR",
        "gl":             "FR",
        "hl":             "fr",
    }
    try:
        run = client.actor("563JCPLOqM1kMmbbP").call(run_input=run_input)

        # Use attribute access instead of dictionary access
        dataset_id = run.default_dataset_id

        for item in client.dataset(dataset_id).iterate_items():
            # Debug: uncomment to see raw item structure
            # print(item)
            results = item.get("results", [])
            for r in results:
                url = r.get("url") or r.get("link") or ""
                if "linkedin.com/company/" in url:
                    return url

    except Exception as e:
        print(f"  Apify error: {e}")
    return None

# --- Main ---

def find_and_save_linkedin_urls(input_csv, company_col, output_csv=None):
    if output_csv is None:
        output_csv = input_csv

    df = pd.read_csv(input_csv)
    if company_col not in df.columns:
        raise ValueError(f"Column '{company_col}' not found. Available: {list(df.columns)}")

    if "linkedin_url" not in df.columns:
        df["linkedin_url"] = None

    checkpoint = load_checkpoint()

    # Apply already-found results from checkpoint
    for i, row in df.iterrows():
        name = str(row[company_col]).strip()
        if name in checkpoint:
            df.at[i, "linkedin_url"] = checkpoint[name]

    pending = df[df["linkedin_url"].isna()].index.tolist()
    total   = len(df)
    print(f"Total companies : {total}")
    print(f"Already done    : {total - len(pending)}")
    print(f"Remaining       : {len(pending)}\n")

    found_since_last_save = 0

    for count, i in enumerate(pending):
        name = str(df.at[i, company_col]).strip()
        print(f"[{count+1}/{len(pending)}] Searching: {name}")

        url = find_linkedin_url(name)
        df.at[i, "linkedin_url"]  = url if url else "Not found"
        checkpoint[name]          = url if url else "Not found"
        print(f"  → {url or 'Not found'}")

        save_checkpoint(checkpoint)
        found_since_last_save += 1

        if found_since_last_save >= SAVE_EVERY:
            df.to_csv(output_csv, index=False, encoding="utf-8-sig")
            print(f"  💾 CSV saved ({output_csv})")
            found_since_last_save = 0

        time.sleep(random.uniform(2, 4))

    # Final save
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\nDone. Results saved to {output_csv}")

    found     = df[(df["linkedin_url"].notna()) & (df["linkedin_url"] != "Not found")]
    not_found = df[df["linkedin_url"] == "Not found"]
    print(f"Found     : {len(found)}")
    print(f"Not found : {len(not_found)}")

    return df



SCRIPT_DIR = Path(__file__).resolve().parent


OUTPUT_DIR = SCRIPT_DIR.parent / "output"


input_file_path = OUTPUT_DIR / "apii_industrial_ALL.csv"
output_file_path = OUTPUT_DIR / "apii_industrial_lkdn_ALL.csv"


find_and_save_linkedin_urls(
    input_csv=str(input_file_path),
    company_col="name",
    output_csv=str(output_file_path),
)