import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

def fetch_page(url: str):
    """Faz o download do HTML de uma URL."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"  [ERRO] Falha ao acessar {url}: {e}")
        return None


def clean_title(text: str) -> str:
    """
    Corrige títulos com palavras coladas (falta de espaço no HTML).
    Ex: 'DesenvolvimentoBackendJunior' → 'Desenvolvimento Backend Junior'
    """
    # Espaço entre minúscula→maiúscula e número→letra
    text = re.sub(r'([a-záéíóúàãõâêîôû])([A-ZÁÉÍÓÚÀÃÕÂÊÎÔÛ])', r'\1 \2', text)
    text = re.sub(r'([0-9])([A-Za-z])', r'\1 \2', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def clean_adzuna_link(href: str) -> str:
    """
    Converte links de redirecionamento do Adzuna para o link direto de detalhes.
    Ex: /land/ad/123456?... → /details/123456
    """
    m = re.search(r'/(?:land/ad|details)/(\d+)', href)
    if m:
        return f"https://www.adzuna.com.br/details/{m.group(1)}"
    return href


def parse_jobs(html: str, base_url: str, site_name: str):
    """
    Extrai vagas de emprego de uma página HTML.
    Suporta: LinkedIn, Indeed, Gupy, Vagas.com, InfoJobs, Adzuna.
    Retorna lista de dicts com: title, location, link, site_name.
    """
    soup = BeautifulSoup(html, "lxml")
    jobs = []
    found = set()

    def add_job(title, href, location=""):
        title = clean_title(title)
        if not title or len(title) < 5 or len(title) > 200:
            return
        if href and href.startswith("http"):
            link = href
        elif href:
            link = base_url.rstrip("/") + "/" + href.lstrip("/")
        else:
            link = base_url
        key = title.lower()
        if key not in found:
            found.add(key)
            jobs.append({
                "title": title,
                "location": location.strip(),
                "link": link,
                "site_name": site_name,
            })

    # ── LinkedIn ──────────────────────────────────────────────────────
    for card in soup.find_all("div", class_=lambda c: c and "job-card-container" in " ".join(c)):
        title_el    = card.find("a", class_=lambda c: c and "job-card-container__link" in " ".join(c))
        location_el = card.find(class_=lambda c: c and "job-card-container__metadata" in " ".join(c))
        if title_el:
            add_job(title_el.get_text(strip=True), title_el.get("href", ""),
                    location_el.get_text(strip=True) if location_el else "")

    # ── Indeed ────────────────────────────────────────────────────────
    for card in soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in " ".join(c)):
        title_el    = card.find("h2", class_=lambda c: c and "jobTitle" in " ".join(c))
        location_el = card.find(class_=lambda c: c and "companyLocation" in " ".join(c))
        a_el = title_el.find("a") if title_el else None
        if a_el:
            add_job(a_el.get_text(strip=True), a_el.get("href", ""),
                    location_el.get_text(strip=True) if location_el else "")

    # ── Gupy ──────────────────────────────────────────────────────────
    for card in soup.find_all(class_=lambda c: c and "job-card" in " ".join(c)):
        title_el    = card.find("h3")
        location_el = card.find(class_=lambda c: c and "location" in " ".join(c))
        a_el = card.find("a")
        if title_el:
            add_job(title_el.get_text(strip=True), a_el.get("href", "") if a_el else "",
                    location_el.get_text(strip=True) if location_el else "")

    # ── Vagas.com ─────────────────────────────────────────────────────
    for card in soup.find_all(["article", "li"], class_=lambda c: c and any(
            k in " ".join(c).lower() for k in ["vaga", "job-item", "resultado"])):
        title_el    = card.find(["h2", "h3", "a"])
        location_el = card.find(class_=lambda c: c and any(
            k in " ".join(c).lower() for k in ["cidade", "local", "location"]))
        if not title_el:
            continue
        href = title_el.get("href", "") if title_el.name == "a" else ""
        if not href:
            a = title_el.find("a") or title_el.find_parent("a")
            href = a.get("href", "") if a else ""
        add_job(title_el.get_text(strip=True), href,
                location_el.get_text(strip=True) if location_el else "")

    # ── InfoJobs ──────────────────────────────────────────────────────
    for card in soup.find_all("div", class_=lambda c: c and "OfferCard" in " ".join(c)):
        title_el    = card.find("a", class_=lambda c: c and "title" in " ".join(c).lower())
        location_el = card.find(class_=lambda c: c and any(
            k in " ".join(c).lower() for k in ["location", "cidade", "local"]))
        if not title_el:
            title_el = card.find(["h2", "h3"])
        if title_el:
            href = title_el.get("href", "") if title_el.name == "a" else ""
            if not href:
                a = title_el.find("a") or title_el.find_parent("a")
                href = a.get("href", "") if a else ""
            add_job(title_el.get_text(strip=True), href,
                    location_el.get_text(strip=True) if location_el else "")

    # ── Adzuna ────────────────────────────────────────────────────────
    for card in soup.find_all("article", class_=lambda c: c and any(
            k in " ".join(c).lower() for k in ["a_res", "job", "result"])):
        title_el    = card.find("p", class_=lambda c: c and "title" in " ".join(c).lower())
        location_el = card.find(class_=lambda c: c and any(
            k in " ".join(c).lower() for k in ["location", "local", "cidade"]))
        if not title_el:
            title_el = card.find(["h2", "h3"])
        if title_el:
            a    = title_el.find("a") if title_el.name != "a" else title_el
            href = a.get("href", "") if a else ""
            # Converte link de redirecionamento para link direto
            if href and "/land/ad/" in href:
                href = clean_adzuna_link(href)
            add_job(title_el.get_text(strip=True), href,
                    location_el.get_text(strip=True) if location_el else "")

    # ── Fallback genérico ─────────────────────────────────────────────
    if not jobs:
        for tag in soup.find_all(["h2", "h3", "h4"]):
            title = tag.get_text(strip=True)
            a = tag.find_parent("a") or tag.find("a")
            href = a.get("href", "") if a else ""
            parent = tag.parent
            loc_el = parent.find(lambda t: t.name in ["span", "p"] and any(
                kw in t.get_text().lower() for kw in ["ceará", "fortaleza", "remot", "brasil"]
            )) if parent else None
            add_job(title, href, loc_el.get_text(strip=True) if loc_el else "")

    return jobs
