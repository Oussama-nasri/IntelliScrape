import os
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

APIFY_KEY = os.getenv("APIFY_KEY")


def scrape_linkedin_company(company_name):
    if not APIFY_KEY:
        raise ValueError("APIFY_KEY not found in environment variables.")

    client = ApifyClient(APIFY_KEY)

    # Fixed Input Schema according to harvestapi/linkedin-company-search
    run_input = {
        "searchQuery": company_name,  # Correct parameter name
        "maxItems": 1,
        "scraperMode": "short"
    }

    print(f"Starting Apify Actor for: {company_name}...")

    # Run the Actor and wait for it to finish
    run = client.actor("taHaRcqil3scbchuI").call(run_input=run_input)

    if not run:
        print("Actor run failed to start.")
        return []

    # Fixed: Use object dot notation (.default_dataset_id) instead of subscripting
    dataset_id = run.default_dataset_id

    # Fetch results from the dataset
    dataset_items = client.dataset(dataset_id).list_items().items
    return dataset_items


if __name__ == "__main__":
    company_name = "actia-engineering-services"

    result_list = scrape_linkedin_company(company_name)

    if result_list:
        # Extract the first matching company found from the search array
        result = result_list[0]

        print("\n=== Extracted Data ===")
        # Note: HarvestAPI outputs camelCase fields or specific strings depending on mode.
        # It's safest to use .get() to avoid throwing errors if fields are missing.
        print(f"Company Name: {result.get('companyName', 'N/A')}")
        print(f"Staff Count: {result.get('secondarySubtitle', 'N/A')}")

        description = result.get('summary', result.get('Description', 'No description available.'))
        print(f"Description: {description[:300]}...")
    else:
        print("\nNo data returned from the scraper.")