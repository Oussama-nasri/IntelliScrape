"""
LinkedIn company page enrichment scraper.
Pulls companies with stage='linkedin_found' (and a linkedin_url),
scrapes their About page, and updates the DB.
"""

import random
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from sqlalchemy.orm import Session

from app.db.models import Company

# ── Config ─────────────────────────────────────────────────────────────────────
RESTART_EVERY          = 25
MIN_PAUSE              = 0.8
MAX_PAUSE              = 1.8
COOLDOWN_AFTER_RESTART = 4
PAGE_LOAD_TIMEOUT      = 15


# ── Driver factory ─────────────────────────────────────────────────────────────

def _get_driver():
    options = Options()
    options.page_load_strategy = "eager"
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2,
    }
    options.add_experimental_option("prefs", prefs)

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR','fr','en-US','en'] });
        """
    })

    return driver


# ── Page scrape ────────────────────────────────────────────────────────────────

def _is_authwall(driver) -> bool:
    return "authwall" in driver.current_url.lower()


def _dismiss_modal(driver):
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass


def _scrape_page(driver, linkedin_url: str) -> dict:
    try:
        driver.get(linkedin_url)
    except TimeoutException:
        pass

    WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    if _is_authwall(driver):
        raise RuntimeError("AUTHWALL_HIT")

    _dismiss_modal(driver)
    driver.execute_script("window.scrollBy(0, 400);")

    if _is_authwall(driver):
        raise RuntimeError("AUTHWALL_HIT")

    data = driver.execute_script("""
        const getText = (sel) => {
            const el = document.querySelector(sel);
            return el ? el.innerText.trim() : "";
        };
        return {
            website:      getText("[data-test-id='about-us__website'] dd a"),
            description:  getText("[data-test-id='about-us__description']"),
            size:         getText("[data-test-id='about-us__size'] dd"),
            sector:       getText("[data-test-id='about-us__industry'] dd"),
            headquarters: getText("[data-test-id='about-us__headquarters'] dd"),
            company_type: getText("[data-test-id='about-us__organizationType'] dd"),
            founded:      getText("[data-test-id='about-us__foundedOn'] dd"),
        };
    """)
    return data


# ── Public entry point ─────────────────────────────────────────────────────────

def enrich_linkedin_profiles(db: Session) -> dict:
    """
    Pulls companies with stage='linkedin_found' that have a linkedin_url,
    scrapes their LinkedIn About page, and updates stage → 'linkedin_enriched'.
    """
    companies = (
        db.query(Company)
        .filter(
            Company.scrape_stage == "linkedin_found",
            Company.linkedin_url.isnot(None),
            Company.linkedin_url != "",
        )
        .all()
    )

    if not companies:
        return {"processed": 0, "enriched": 0, "errors": 0}

    print(f"[linkedin_enrich] {len(companies)} companies to enrich…")

    driver = _get_driver()
    session_count = 0
    enriched = 0
    errors = 0

    try:
        for i, company in enumerate(companies, 1):
            print(f"  [{i}/{len(companies)}] {company.name} → {company.linkedin_url}")

            # Restart browser periodically
            if session_count >= RESTART_EVERY:
                print("  Restarting browser…")
                try:
                    driver.quit()
                except Exception:
                    pass
                time.sleep(COOLDOWN_AFTER_RESTART)
                driver = _get_driver()
                session_count = 0

            def _do_scrape():
                return _scrape_page(driver, company.linkedin_url)

            try:
                data = _do_scrape()

            except RuntimeError as e:
                if "AUTHWALL_HIT" in str(e):
                    print("  ✗ Authwall — restarting…")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    time.sleep(COOLDOWN_AFTER_RESTART)
                    driver = _get_driver()
                    session_count = 0
                    try:
                        data = _do_scrape()
                    except Exception as retry_err:
                        print(f"  ✗ Retry failed: {retry_err}")
                        company.scrape_stage = "linkedin_enriched"
                        db.commit()
                        errors += 1
                        continue
                else:
                    raise

            # Update company record
            company.website      = data.get("website", "")
            company.description  = data.get("description", "")
            company.size         = data.get("size", "")
            company.sector       = data.get("sector", "")
            company.headquarters = data.get("headquarters", "")
            company.company_type = data.get("company_type", "")
            company.founded      = data.get("founded", "")
            company.scrape_stage = "linkedin_enriched"

            db.commit()
            session_count += 1
            enriched += 1

            print(f"  ✓ website={data.get('website')} | size={data.get('size')}")

            time.sleep(random.uniform(MIN_PAUSE, MAX_PAUSE))

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    print(f"[linkedin_enrich] Done. Enriched: {enriched} / Errors: {errors}")
    return {"processed": len(companies), "enriched": enriched, "errors": errors}