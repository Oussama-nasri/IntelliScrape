import requests
import os
from dotenv import load_dotenv
from apify_client import ApifyClient
load_dotenv()

APIFY_KEY = os.getenv("APIFY_KEY")

def scrape_linkedin_company(company_name):
    client = ApifyClient(APIFY_KEY)

    # Prepare the Actor input
    run_input = {
    "maxItems": 1,
    "scraperMode": "short"
}

    # Run the Actor and wait for it to finish
    run = client.actor("taHaRcqil3scbchuI").call(run_input=run_input)

    # Fetch and print Actor results from the run's dataset (if there are any)
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        print(item)
    return client.dataset(run["defaultDatasetId"]).items
if __name__ == "__main__":
    company_name = "actia-engineering-services"

    result = scrape_linkedin_company(company_name)

    if result:
        print("\n=== Extracted Data ===")
        print(f"Employees: {result['Employee Count']}")
        print(f"Description: {result['Description'][:300]}...")  # Truncated print