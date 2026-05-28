from pathlib import Path
import pandas as pd

# Define paths as requested
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent / "output"

input_file_path = OUTPUT_DIR / "apii_industrial_lkdn_ALL.csv"
output_file_path = OUTPUT_DIR / "apii_industrial_lkdn_ALL.csv"


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

    # Record the initial row count
    initial_rows = len(df)

    # 1. Drop rows where the column is completely missing (NaN)
    df = df.dropna(subset=["linkedin_url"])

    # 2. Drop rows where the column is just empty strings or spaces
    df = df[df["linkedin_url"].astype(str).str.strip() != ""]

    # Calculate how many rows were deleted
    final_rows = len(df)
    removed_rows = initial_rows - final_rows

    # Save the cleaned data back to the CSV
    df.to_csv(output_file_path, index=False)

    print(f"Done! Removed {removed_rows} rows with empty 'linkedin_url' fields.")
    print(f"Successfully saved updated data to: {output_file_path}")


if __name__ == "__main__":
    main()