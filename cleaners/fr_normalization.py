import re
from pathlib import Path
import pandas as pd

# Define paths as requested
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent / "output"

input_file_path = OUTPUT_DIR / "apii_industrial_lkdn_ALL.csv"
output_file_path = OUTPUT_DIR / "apii_industrial_lkdn_ALL_fr.csv"


def force_french_linkedin(url):
    if pd.isna(url) or not isinstance(url, str):
        return url

    # Regex breakdown:
    # ^https?:// -> matches http:// or https://
    # ([a-z]{2,3}|www) -> matches subdomains like 'www', 'cl', 'ga', etc.
    # (\.linkedin\.com/.*) -> captures the rest of the URL
    pattern = r"^https?://([a-z]{2,3}|www)(\.linkedin\.com/.*)"

    # Replace the subdomain with 'fr'
    if re.match(pattern, url):
        return re.sub(pattern, r"https://fr\2", url)

    return url


def main():
    # Check if the input file exists before proceeding
    if not input_file_path.exists():
        print(f"Error: The file {input_file_path} does not exist.")
        return

    # Load the CSV
    print(f"Reading data from: {input_file_path}")
    df = pd.read_csv(input_file_path)

    # Check if the column exists
    if "linkedin_url" not in df.columns:
        print("Error: 'linkedin_url' column not found in the CSV.")
        return

    # Apply the transformation
    print("Cleaning LinkedIn URLs to force French locale...")
    df["linkedin_url"] = df["linkedin_url"].apply(force_french_linkedin)

    # Save the cleaned data back to the CSV
    df.to_csv(output_file_path, index=False)
    print(f"Successfully saved cleaned data to: {output_file_path}")


if __name__ == "__main__":
    main()