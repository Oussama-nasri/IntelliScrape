import requests
from bs4 import BeautifulSoup


def get_company_description_ween(company_slug):
    url = f"https://ween.tn/fiche/{company_slug}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            apropos_div = soup.find("div", class_="aprop-empty")

            if apropos_div:
                # Extract text, clean up whitespaces, and return it
                return apropos_div.get_text(separator=" ", strip=True)
            else:
                print(
                    f"[{company_slug}] 'aprop-empty' class not found on page."
                )
                return None
        else:
            print(
                f"[{company_slug}] Failed to fetch page. Status code: {response.status_code}"
            )
            return None

    except requests.exceptions.RequestException as e:
        print(f"[{company_slug}] A network error occurred: {e}")
        return None
