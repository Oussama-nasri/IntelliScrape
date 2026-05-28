from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import time
import random
import csv

# --- Config ---
RESTART_EVERY = 1       # Restart browser every N companies
MIN_PAUSE = 8           # Seconds between companies
MAX_PAUSE = 18
COOLDOWN_AFTER_RESTART = 20  # Seconds to wait after browser restart

# --- Helpers ---

def random_sleep(min_sec=2, max_sec=5):
    time.sleep(random.uniform(min_sec, max_sec))

def get_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US', 'en'] });
        """
    })
    return driver

def is_authwall(driver):
    return "authwall" in driver.current_url

def dismiss_modal(driver):
    try:
        random_sleep(2, 4)
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        random_sleep(1, 2)
    except Exception:
        pass

def extract_field(driver, test_id):
    try:
        el = driver.find_element(By.CSS_SELECTOR, f"[data-test-id='{test_id}'] dd")
        return el.text.strip()
    except Exception:
        return ""

def extract_website(driver):
    try:
        el = driver.find_element(By.CSS_SELECTOR, "[data-test-id='about-us__website'] dd a")
        return el.text.strip().split("\n")[0]
    except Exception:
        return ""

def extract_description(driver):
    try:
        el = driver.find_element(By.CSS_SELECTOR, "[data-test-id='about-us__description']")
        return el.text.strip()
    except Exception:
        return ""

# --- Single company scraper ---

def scrape_company(driver, url):
    driver.get(url)
    random_sleep(3, 6)

    # Check for authwall immediately after load
    if is_authwall(driver):
        raise Exception("AUTHWALL_HIT")

    dismiss_modal(driver)

    # Human-like scroll
    for _ in range(3):
        driver.execute_script("window.scrollBy(0, 300);")
        random_sleep(0.5, 1.5)

    # Check again after scroll (modal can trigger redirect)
    if is_authwall(driver):
        raise Exception("AUTHWALL_HIT")

    return {
        "url":          url,
        "website":      extract_website(driver),
        "description":  extract_description(driver),
        "size":         extract_field(driver, "about-us__size"),
        "sector":       extract_field(driver, "about-us__industry"),
        "headquarters": extract_field(driver, "about-us__headquarters"),
        "type":         extract_field(driver, "about-us__organizationType"),
        "founded":      extract_field(driver, "about-us__foundedOn"),
    }

# --- Multi-company scraper with browser restart ---

def scrape_companies(company_urls, output_csv="results.csv"):
    results = []
    driver = get_driver()
    companies_in_session = 0

    try:
        for i, url in enumerate(company_urls):
            print(f"\n[{i+1}/{len(company_urls)}] {url}")

            # Restart browser every RESTART_EVERY companies
            if companies_in_session >= RESTART_EVERY:
                print(f"  Restarting browser (session limit reached)...")
                driver.quit()
                time.sleep(COOLDOWN_AFTER_RESTART)
                driver = get_driver()
                companies_in_session = 0

            try:
                data = scrape_company(driver, url)
                results.append(data)
                companies_in_session += 1
                print(f"  ✓ website={data['website']} | size={data['size']}")

            except Exception as e:
                err = str(e)
                if "AUTHWALL_HIT" in err:
                    print(f"  ✗ Authwall hit! Restarting browser and retrying once...")
                    driver.quit()
                    time.sleep(COOLDOWN_AFTER_RESTART)
                    driver = get_driver()
                    companies_in_session = 0

                    # Retry once after fresh browser
                    try:
                        data = scrape_company(driver, url)
                        results.append(data)
                        companies_in_session += 1
                        print(f"  ✓ Retry succeeded: {data['website']}")
                    except Exception as e2:
                        print(f"  ✗ Retry failed: {e2}")
                        results.append({"url": url, "error": str(e2)})
                else:
                    print(f"  ✗ Error: {err}")
                    results.append({"url": url, "error": err})

            # Random pause between companies
            if i < len(company_urls) - 1:
                pause = random.uniform(MIN_PAUSE, MAX_PAUSE)
                print(f"  Waiting {pause:.1f}s...")
                time.sleep(pause)

    finally:
        driver.quit()

    # Save to CSV
    keys = ["url", "website", "description", "size", "sector", "headquarters", "type", "founded", "error"]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDone. {len(results)} results saved to {output_csv}")
    return results

# --- Run ---

companies = [
    "https://fr.linkedin.com/company/actia-engineering-services",
    "https://fr.linkedin.com/company/vermeg",
    "https://fr.linkedin.com/company/sofrecom-tunisie",
]

print(scrape_companies(companies))

