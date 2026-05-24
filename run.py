#!/usr/bin/env python3
# run.py — Single entry point for the Tunisia company scraper pipeline
#
# Usage:
#   python run.py                  # Run all three stages
#   python run.py --skip-rne       # APII only (no RNE enrichment)
#   python run.py --rne-only       # RNE enrichment on existing CSV
#   python run.py --industrial     # Industrial scrape only
#   python run.py --services       # Services scrape only
#   python run.py --rne-limit 50   # Enrich only first 50 companies

import argparse
import sys

from scrapers.apii_industrial import scrape_industrial ,scrap_industrial_all
from exporters.csv_exporter    import save_to_csv
from config import INDUSTRIAL_CSV


def main():
    print("\n" + "="*60)
    print("STAGE 1: APII Industrial Directory")
    print("="*60)
    industrial_data = scrap_industrial_all()
    save_to_csv(industrial_data, INDUSTRIAL_CSV)

    print("\n✅ Pipeline complete. Results saved to ./output/")


if __name__ == "__main__":
    main()
