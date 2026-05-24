# exporters/csv_exporter.py
"""
Saves a list of company dicts to a CSV file using pandas.
Handles deduplication and appending across paginated runs.
"""

import os
import pandas as pd


def save_to_csv(companies: list[dict], filepath: str, deduplicate: bool = True) -> int:
    """
    Write companies to a CSV file.

    - If the file already exists, new rows are appended and duplicates removed.
    - Returns the number of NEW unique rows written.

    Args:
        companies:   List of company dicts from the parser.
        filepath:    Destination path (e.g. "output/apii_industrial.csv").
        deduplicate: If True, drop rows where 'name' is an exact duplicate.
    """
    if not companies:
        print(f"  [exporter] No data to save → {filepath}")
        return 0

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    new_df = pd.DataFrame(companies)

    # If file exists, load and merge
    if os.path.exists(filepath):
        existing_df = pd.read_csv(filepath, dtype=str)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined_df = new_df

    if deduplicate:
        before = len(combined_df)
        combined_df = combined_df.drop_duplicates(subset=["name"])
        removed = before - len(combined_df)
        if removed:
            print(f"  [exporter] Removed {removed} duplicate rows")

    combined_df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"  [exporter] Saved {len(combined_df)} total rows → {filepath}")
    return len(new_df)
