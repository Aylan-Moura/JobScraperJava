"""
Scraper do LinkedIn usando Selenium + cookies de sessão.

Como configurar:
  1. Instale a extensão "Cookie-Editor" no Chrome
     https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm
  2. Acesse linkedin.com e faça login normalmente
  3. Clique no ícone da extensão → Export → Export as JSON
  4. Salve o arquivo em: cookies/linkedin.json  (na raiz do projeto)
"""

import os
import json
import time
import random
import re
from pathlib import Path
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

COOKIES_FILE = Path("/cookies/linkedin.json")


def _load_cookies(driver):
    """
    Carrega cookies do LinkedIn exportados pelo Cookie-Editor.
    Retorna True se os cookies foram carregados com sucesso.
    """
    if not COOKIES_FILE.exists():
        return False

    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        # Precisa estar na página do LinkedIn antes de setar cookies
        driver.get("https://www.linkedin.com")
        time.sleep(2)

        for cookie in cookies:
            try:
                # Remove campos que o Selenium não aceita
                cookie.pop("sameSite", None)
                cookie.pop("storeId", None)
                cookie.pop("id", None)
                # Garante que o domínio está correto
                cookie["domain"] = ".linkedin.com"
                driver.add_cookie(cookie)
            except Exception:
                pass  # Ignora cookies inválidos individualmente

        print("   🍪 Cookies do LinkedIn carregados com sucesso")
        return True

    except Exception as e:
        print(f"   ⚠️  Erro ao carregar cookies: {e}")
        return False


def _build_driver() -> webdriver.Chrome:
    """Cria Chrome headless com máxima camuflagem anti-bot."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=pt-BR,pt;q=0.9")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    service = Service("/usr/bin/chromedriver")
    driver  = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins',   {get: () => [1, 2, 3]});
            Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en']});
            window.chrome = { runtime: {} };
        """
    })
    return driver


def _human_scroll(driver, scrolls: int = 6):
    """Simula scroll humano com variação de velocidade."""
    for _ in range(scrolls):
        driver.execute_script(f"window.scrollBy(0, {random.randint(400, 900)});")
        time.sleep(random.uniform(0.8, 2.0))


def _clean_title(text: str) -> str:
    """Corrige títulos com palavras coladas no HTML."""
    text = re.sub(r'([a-záéíóúàãõâêîôû])([A-ZÁÉÍÓÚÀÃÕÂÊÎÔÛ])', r'\1 \2', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _extract_jobs(html: str, url: str, site_name: str) -> list[dict]:
    """Extrai vagas do HTML renderizado pelo Selenium."""
    soup  = BeautifulSoup(html, "lxml")
    jobs  = []
    found = set()

    def add_job(title, href, location=""):
        title = _clean_title(title)
        if not title or len(title) < 5 or len(title) > 200:
            return
        link = (href if href and href.startswith("http")
                else "https://www.linkedin.com" + href if href and href.startswith("/")
                else url)
        link = link.split("?")[0] if "linkedin.com/jobs/view" in link else link
        key  = title.lower()
        if key not in found:
            found.add(key)
            jobs.append({"title": title, "location": location.strip(),
                         "link": link, "site_name": site_name})

    # Versão logada: job-card-container
    for card in soup.find_all("div", class_=lambda c: c and "job-card-container" in " ".join(c)):
        t = card.find("a", class_=lambda c: c and "job-card-container__link" in " ".join(c))
        l = card.find(class_=lambda c: c and "job-card-container__metadata" in " ".join(c))
        if t:
            add_job(t.get_text(strip=True), t.get("href", ""),
                    l.get_text(strip=True) if l else "")

    # Versão pública: base-card
    for card in soup.find_all("div", class_=lambda c: c and "base-card" in " ".join(c)):
        t = card.find(["h3", "h4"])
        l = card.find("span", class_=lambda c: c and "job-search-card__location" in " ".join(c))
        a = card.find("a", class_=lambda c: c and "base-card__full-link" in " ".join(c))
        if t:
            add_job(t.get_text(strip=True), a.get("href", "") if a else "",
                    l.get_text(strip=True) if l else "")

    # Versão pública antiga: result-card
    for card in soup.find_all("li", class_=lambda c: c and "result-card" in " ".join(c)):
        t = card.find(["h3", "h4"])
        l = card.find("span", class_=lambda c: c and "location" in " ".join(c).lower())
        a = card.find("a")
        if t:
            add_job(t.get_text(strip=True), a.get("href", "") if a else "",
                    l.get_text(strip=True) if l else "")

    return jobs


def fetch_linkedin_jobs(url: str, site_name: str = "linkedin.com") -> list[dict]:
    """
    Acessa URL do LinkedIn com Selenium.
    Se cookies/linkedin.json existir, injeta a sessão autenticada.
    """
    has_cookies = COOKIES_FILE.exists()
    print(f"   🤖 Chrome headless → LinkedIn {'🍪 com cookies' if has_cookies else '(sem login)'}...")

    if not has_cookies:
        print("   ℹ️  Para melhores resultados, exporte seus cookies do LinkedIn:")
        print("      1. Instale Cookie-Editor no Chrome")
        print("      2. Faça login no linkedin.com")
        print("      3. Export → Export as JSON → salve em cookies/linkedin.json")

    driver = None
    jobs   = []

    try:
        driver = _build_driver()

        # Injeta cookies se disponíveis
        if has_cookies:
            _load_cookies(driver)
            time.sleep(1)

        # Acessa a URL de busca
        driver.get(url)
        time.sleep(random.uniform(2.5, 4.0))

        # Verifica se foi redirecionado para login
        current = driver.current_url
        if "authwall" in current or "/login" in current or "checkpoint" in current:
            if has_cookies:
                print("   ⚠️  Cookies expirados — faça login novamente e exporte os cookies.")
            else:
                print("   ⚠️  LinkedIn exigiu login. Exporte os cookies conforme instruções acima.")
            return []

        # Aguarda cards
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                    "li.result-card, div.base-card, div.job-card-container, "
                    "ul.jobs-search__results-list"))
            )
        except TimeoutException:
            print("   ⚠️  Timeout aguardando cards")

        _human_scroll(driver, scrolls=5)

        jobs = _extract_jobs(driver.page_source, url, site_name)
        status = f"✅ {len(jobs)} vagas" if jobs else "⚠️  0 vagas (possível bloqueio ou cookies expirados)"
        print(f"   {status}")

    except WebDriverException as e:
        print(f"   ❌ Erro Selenium: {e}")
    finally:
        if driver:
            driver.quit()

    return jobs
