from pathlib import Path
import csv
import time
import random

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from selenium.webdriver.chrome.options import Options

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import TimeoutException


# =========================
# Paths
# =========================

SCRIPT_DIR = Path(__file__).resolve().parent

OUTPUT_DIR = SCRIPT_DIR.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

input_file_path = OUTPUT_DIR / "apii_industrial_lkdn_ALL_fr.csv"

output_file_path = OUTPUT_DIR / "apii_industrial_lkdn_ALL_fr_final.csv"


# =========================
# Config
# =========================

# Restart browser every X companies
RESTART_EVERY = 25

# Small random pause between requests
MIN_PAUSE = 0.8
MAX_PAUSE = 1.8

# Cooldown after browser restart
COOLDOWN_AFTER_RESTART = 4

# Just logging frequency now
CHECKPOINT_SAVE_EVERY = 20

# Skip already processed rows
ENABLE_CHECKPOINTS = True

# Page load timeout
PAGE_LOAD_TIMEOUT = 15


# =========================
# Helpers
# =========================

def random_sleep(min_sec=0.8, max_sec=1.8):
    time.sleep(random.uniform(min_sec, max_sec))


def get_driver():

    options = Options()

    # Faster page loading
    options.page_load_strategy = "eager"

    # Headless
    options.add_argument("--headless=new")

    # Window
    options.add_argument("--window-size=1920,1080")

    # Linux/VPS stability
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Performance
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")

    # Anti-detection
    options.add_argument("--disable-blink-features=AutomationControlled")

    options.add_experimental_option(
        "excludeSwitches",
        ["enable-automation"]
    )

    options.add_experimental_option(
        "useAutomationExtension",
        False
    )

    # Disable heavy resources
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2,
    }

    options.add_experimental_option("prefs", prefs)

    # Random user agent
    user_agents = [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    ]

    options.add_argument(
        f"--user-agent={random.choice(user_agents)}"
    )

    driver = webdriver.Chrome(options=options)

    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

    # Anti-detection JS
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(
                    navigator,
                    'webdriver',
                    { get: () => undefined }
                );

                Object.defineProperty(
                    navigator,
                    'plugins',
                    { get: () => [1, 2, 3] }
                );

                Object.defineProperty(
                    navigator,
                    'languages',
                    { get: () => ['fr-FR', 'fr', 'en-US', 'en'] }
                );
            """
        }
    )

    return driver


def is_authwall(driver):
    return "authwall" in driver.current_url.lower()


def dismiss_modal(driver):
    try:
        driver.find_element(
            By.TAG_NAME,
            "body"
        ).send_keys(Keys.ESCAPE)

    except Exception:
        pass


# =========================
# CSV Helpers
# =========================

OUTPUT_FIELDS = [
    "name",
    "activity",
    "governorate",
    "phone",
    "linkedin_url",
    "website",
    "description",
    "size",
    "sector",
    "headquarters",
    "type",
    "founded",
    "error",
]


def load_input_rows():

    with open(input_file_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_processed_urls():

    processed = set()

    if not output_file_path.exists():
        return processed

    with open(output_file_path, "r", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for row in reader:

            linkedin_url = row.get(
                "linkedin_url",
                ""
            ).strip()

            if linkedin_url:
                processed.add(linkedin_url)

    return processed


# =========================
# LinkedIn Scraper
# =========================

def scrape_company(driver, linkedin_url):

    try:
        driver.get(linkedin_url)

    except TimeoutException:
        pass

    # Wait for body
    WebDriverWait(driver, 6).until(
        EC.presence_of_element_located(
            (By.TAG_NAME, "body")
        )
    )

    if is_authwall(driver):
        raise Exception("AUTHWALL_HIT")

    dismiss_modal(driver)

    # Small scroll only once
    driver.execute_script(
        "window.scrollBy(0, 400);"
    )

    if is_authwall(driver):
        raise Exception("AUTHWALL_HIT")

    # Extract everything in ONE JS call
    data = driver.execute_script("""
        const getText = (selector) => {
            const el = document.querySelector(selector);
            return el ? el.innerText.trim() : "";
        };

        return {

            website: getText(
                "[data-test-id='about-us__website'] dd a"
            ),

            description: getText(
                "[data-test-id='about-us__description']"
            ),

            size: getText(
                "[data-test-id='about-us__size'] dd"
            ),

            sector: getText(
                "[data-test-id='about-us__industry'] dd"
            ),

            headquarters: getText(
                "[data-test-id='about-us__headquarters'] dd"
            ),

            type: getText(
                "[data-test-id='about-us__organizationType'] dd"
            ),

            founded: getText(
                "[data-test-id='about-us__foundedOn'] dd"
            ),
        };
    """)

    return data


# =========================
# Main
# =========================

def scrape_companies():

    input_rows = load_input_rows()

    processed_urls = (
        load_processed_urls()
        if ENABLE_CHECKPOINTS
        else set()
    )

    print(f"Loaded {len(input_rows)} rows")
    print(f"Already processed: {len(processed_urls)}")

    driver = get_driver()

    companies_in_session = 0
    saved_since_checkpoint = 0

    file_exists = output_file_path.exists()

    with open(
        output_file_path,
        "a",
        newline="",
        encoding="utf-8"
    ) as outfile:

        writer = csv.DictWriter(
            outfile,
            fieldnames=OUTPUT_FIELDS,
            extrasaction="ignore"
        )

        if not file_exists:
            writer.writeheader()

        try:

            for idx, row in enumerate(input_rows, start=1):

                linkedin_url = (
                    row.get("linkedin_url", "")
                    .strip()
                )

                if not linkedin_url:
                    print(f"\n[{idx}] Missing linkedin_url")
                    continue

                # =====================
                # Skip already processed
                # =====================

                if linkedin_url in processed_urls:

                    print(
                        f"\n[{idx}] SKIP already processed:"
                        f" {linkedin_url}"
                    )

                    continue

                print(
                    f"\n[{idx}/{len(input_rows)}]"
                    f" {linkedin_url}"
                )

                # =====================
                # Restart browser
                # =====================

                if companies_in_session >= RESTART_EVERY:

                    print(
                        "  Restarting browser..."
                    )

                    try:
                        driver.quit()
                    except Exception:
                        pass

                    time.sleep(COOLDOWN_AFTER_RESTART)

                    driver = get_driver()

                    companies_in_session = 0

                # =====================
                # Scrape
                # =====================

                try:

                    scraped = scrape_company(
                        driver,
                        linkedin_url
                    )

                    result = {
                        **row,
                        **scraped,
                        "error": "",
                    }

                    writer.writerow(result)
                    outfile.flush()

                    processed_urls.add(linkedin_url)

                    companies_in_session += 1
                    saved_since_checkpoint += 1

                    print(
                        f"  ✓ "
                        f"website={scraped['website']} "
                        f"| size={scraped['size']}"
                    )

                except Exception as e:

                    err = str(e)

                    # =====================
                    # Authwall recovery
                    # =====================

                    if "AUTHWALL_HIT" in err:

                        print(
                            "  ✗ Authwall hit!"
                            " Restarting browser..."
                        )

                        try:
                            driver.quit()
                        except Exception:
                            pass

                        time.sleep(COOLDOWN_AFTER_RESTART)

                        driver = get_driver()

                        companies_in_session = 0

                        # Retry once
                        try:

                            scraped = scrape_company(
                                driver,
                                linkedin_url
                            )

                            result = {
                                **row,
                                **scraped,
                                "error": "",
                            }

                            writer.writerow(result)
                            outfile.flush()

                            processed_urls.add(linkedin_url)

                            companies_in_session += 1
                            saved_since_checkpoint += 1

                            print(
                                "  ✓ Retry succeeded"
                            )

                        except Exception as retry_error:

                            print(
                                f"  ✗ Retry failed:"
                                f" {retry_error}"
                            )

                            result = {
                                **row,
                                "website": "",
                                "description": "",
                                "size": "",
                                "sector": "",
                                "headquarters": "",
                                "type": "",
                                "founded": "",
                                "error": str(retry_error),
                            }

                            writer.writerow(result)
                            outfile.flush()

                            processed_urls.add(linkedin_url)

                    else:

                        print(f"  ✗ Error: {err}")

                        result = {
                            **row,
                            "website": "",
                            "description": "",
                            "size": "",
                            "sector": "",
                            "headquarters": "",
                            "type": "",
                            "founded": "",
                            "error": err,
                        }

                        writer.writerow(result)
                        outfile.flush()

                        processed_urls.add(linkedin_url)

                # =====================
                # Checkpoint log
                # =====================

                if (
                    saved_since_checkpoint
                    >= CHECKPOINT_SAVE_EVERY
                ):

                    print(
                        f"  💾 Checkpoint saved -> "
                        f"{output_file_path.name}"
                    )

                    saved_since_checkpoint = 0

                # =====================
                # Random pause
                # =====================

                pause = random.uniform(
                    MIN_PAUSE,
                    MAX_PAUSE
                )

                print(
                    f"  Waiting {pause:.1f}s..."
                )

                time.sleep(pause)

        finally:

            try:
                driver.quit()
            except Exception:
                pass

    print(
        f"\nDone. Results saved to:\n"
        f"{output_file_path}"
    )


# =========================
# Run
# =========================

if __name__ == "__main__":
    scrape_companies()