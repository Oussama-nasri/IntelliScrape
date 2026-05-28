import pandas as pd
import serpapi
import time
import random
import json
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

SERPAPI_KEY     = os.getenv("SERPAPI_KEY")
print("key", SERPAPI_KEY)
CHECKPOINT_FILE = "search_checkpoint.json"
SAVE_EVERY      = 5  # Save CSV every N links found

client = serpapi.Client(api_key=SERPAPI_KEY)


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
    try:
        results = client.search({
            "engine":        "google",
            "q":             f"{company_name} site:linkedin.com/company",
            "google_domain": "google.fr",
            "hl":            "fr",
            "gl":            "fr",
            "num":           5,
        })
        for r in results.get("organic_results", []):
            url = r.get("link", "")
            if "linkedin.com/company/" in url:
                return url
    except Exception as e:
        print(f"  SerpAPI error: {e}")
    return None

# --- Main function ---

def find_and_save_linkedin_urls(input_csv, company_col, output_csv=None):
    """
    input_csv    : path to your CSV file
    company_col  : name of the column containing company names
    output_csv   : output path (defaults to overwriting input_csv)
    """
    if output_csv is None:
        output_csv = input_csv

    # Load CSV
    df = pd.read_csv(input_csv)
    if company_col not in df.columns:
        raise ValueError(f"Column '{company_col}' Not found. Available: {list(df.columns)}")

    # Add linkedin_url column if it doesn't exist
    if "linkedin_url" not in df.columns:
        df["linkedin_url"] = None

    # Load checkpoint (name -> url mapping)
    checkpoint = load_checkpoint()

    # Apply checkpoint results already found to dataframe
    for i, row in df.iterrows():
        name = str(row[company_col]).strip()
        if name in checkpoint:
            df.at[i, "linkedin_url"] = checkpoint[name]

    # Figure out which rows still need processing
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
        df.at[i, "linkedin_url"] = url if url else "Not found"
        checkpoint[name]         = url if url else "Not found"

        print(f"  → {url or ''}")

        # Save checkpoint after every result
        save_checkpoint(checkpoint)
        found_since_last_save += 1

        # Save CSV every SAVE_EVERY results
        if found_since_last_save >= SAVE_EVERY:
            df.to_csv(output_csv, index=False, encoding="utf-8-sig")
            print(f"  💾 CSV saved ({output_csv})")
            found_since_last_save = 0

        time.sleep(random.uniform(2, 4))

    # Final save
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\nDone. Results saved to {output_csv}")

    # Summary
    found     = df[df["linkedin_url"].notna() & (df["linkedin_url"] != "Not found")]
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