"""
serp_scraper.py — Busca vagas via SerpAPI (Google Search)
Stack:  Java (Spring, Quarkus, Maven, Hibernate)
Níveis: Estágio, Junior, Senior
Locais: Ceará (presencial) | Brasil (remoto)
"""

import os
import re
import requests
from datetime import datetime, timedelta

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SERPAPI_URL = "https://serpapi.com/search"

SITES_BR = (
    "site:vagas.com.br OR site:infojobs.com.br OR site:adzuna.com.br"
)
SITES_EMPRESAS = (
    "site:carreiras.inter.co OR site:job-boards.greenhouse.io OR "
    "site:carreiras.itau.com.br OR site:jobs.lever.co OR site:picpay.com"
)
LINKEDIN = "site:linkedin.com/jobs"

SERP_QUERIES = [

    # ══ CEARÁ — ESTÁGIO ═══════════════════════════════════════════════
    f'{SITES_BR} "java" ("estágio" OR "estagio") "Fortaleza" OR "Ceará"',
    f'{LINKEDIN} "java" ("estágio" OR "estagio" OR "intern") "Fortaleza" OR "Ceará"',
    f'{SITES_BR} "spring" ("estágio" OR "estagio") "Fortaleza" OR "Ceará"',

    # ══ CEARÁ — JUNIOR ════════════════════════════════════════════════
    f'{SITES_BR} "java junior" "Fortaleza" OR "Ceará"',
    f'{SITES_BR} "java júnior" "Fortaleza" OR "Ceará"',
    f'{SITES_BR} "spring boot junior" "Fortaleza" OR "Ceará"',
    f'{LINKEDIN} "java junior" "Fortaleza" OR "Ceará"',

    # ══ CEARÁ — SENIOR ════════════════════════════════════════════════
    f'{SITES_BR} "java senior" OR "java sênior" "Fortaleza" OR "Ceará"',
    f'{SITES_BR} "spring boot senior" OR "spring boot sênior" "Fortaleza" OR "Ceará"',
    f'{LINKEDIN} "java senior" OR "java sênior" "Fortaleza" OR "Ceará"',

    # ══ REMOTO BRASIL — ESTÁGIO ═══════════════════════════════════════
    f'{SITES_BR} "java" ("estágio" OR "estagio") ("remoto" OR "home office")',
    f'{LINKEDIN} "java" ("estágio" OR "intern") ("remoto" OR "remote") Brasil',
    f'{SITES_EMPRESAS} "java" ("estágio" OR "estagio" OR "intern")',

    # ══ REMOTO BRASIL — JUNIOR ════════════════════════════════════════
    f'{SITES_BR} "java junior" ("remoto" OR "home office") Brasil',
    f'{SITES_BR} "java júnior" ("remoto" OR "home office")',
    f'{SITES_BR} "spring boot" "junior" ("remoto" OR "home office")',
    f'{LINKEDIN} "java junior" ("remoto" OR "remote") Brasil',
    f'{SITES_EMPRESAS} "java" ("junior" OR "júnior")',

    # ══ REMOTO BRASIL — SENIOR ════════════════════════════════════════
    f'{SITES_BR} "java senior" ("remoto" OR "home office") Brasil',
    f'{SITES_BR} "java sênior" ("remoto" OR "home office")',
    f'{SITES_BR} "spring boot" "senior" ("remoto" OR "home office")',
    f'{LINKEDIN} "java senior" OR "java sênior" ("remoto" OR "remote") Brasil',
    f'{SITES_EMPRESAS} "java" ("senior" OR "sênior")',

]


def normalize_linkedin_url(url: str) -> str:
    """
    Normaliza URLs do LinkedIn para o formato canônico com só o job ID.
    Ex: br.linkedin.com/jobs/view/123?trk=abc → linkedin.com/jobs/view/123
    """
    m = re.search(r"/jobs/view/(\d+)", url)
    if m:
        return f"https://www.linkedin.com/jobs/view/{m.group(1)}"
    return url


def extract_date_from_snippet(snippet: str) -> datetime | None:
    """
    Extrai data relativa do snippet do Google.
    Ex: '3 days ago', 'há 2 dias', '1 week ago'
    """
    now  = datetime.now()
    text = snippet.lower()

    patterns = [
        (r"(\d+)\s+day[s]?\s+ago",    "days"),
        (r"(\d+)\s+hour[s]?\s+ago",   "hours"),
        (r"(\d+)\s+week[s]?\s+ago",   "weeks"),
        (r"(\d+)\s+month[s]?\s+ago",  "months"),
        (r"h[aá]\s+(\d+)\s+dia",      "days"),
        (r"h[aá]\s+(\d+)\s+hora",     "hours"),
        (r"h[aá]\s+(\d+)\s+semana",   "weeks"),
        (r"h[aá]\s+(\d+)\s+m[eê]s",  "months"),
        (r"(\d+)\s+dias?\s+atr",      "days"),
        (r"\bjust posted\b|\bhoje\b|\btoday\b", "today"),
        (r"\byesterday\b|\bontem\b",   "yesterday"),
    ]

    for pattern, unit in patterns:
        m = re.search(pattern, text)
        if m:
            if unit == "today":
                return now
            if unit == "yesterday":
                return now - timedelta(days=1)
            n = int(m.group(1))
            if unit == "days":
                return now - timedelta(days=n)
            if unit == "hours":
                return now - timedelta(hours=n)
            if unit == "weeks":
                return now - timedelta(weeks=n)
            if unit == "months":
                return now - timedelta(days=n * 30)
    return None


def fetch_serp_jobs() -> list:
    """Busca vagas via SerpAPI e retorna lista no formato padrão."""
    if not SERPAPI_KEY:
        print("  [SERP] ⚠️  SERPAPI_KEY não configurada — pulando SerpAPI.")
        return []

    all_jobs   = []
    seen_links = set()

    for query in SERP_QUERIES:
        params = {
            "engine":  "google",
            "q":       query,
            "api_key": SERPAPI_KEY,
            "hl":      "pt",
            "gl":      "br",
            "num":     10,
        }

        try:
            resp = requests.get(SERPAPI_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [SERP] ❌ Erro: '{query[:55]}...' → {e}")
            continue

        results = data.get("organic_results", [])
        novos   = 0

        for r in results:
            link    = r.get("link", "")
            title   = r.get("title", "").strip()
            snippet = r.get("snippet", "")

            if not link or not title:
                continue

            # Normaliza URL do LinkedIn para evitar duplicatas
            if "linkedin.com/jobs" in link:
                link = normalize_linkedin_url(link)

            if link in seen_links:
                continue

            # Detecta localização pelo snippet
            location = ""
            for termo in ["fortaleza", "ceará", "ceara", "sobral",
                          "juazeiro", "remoto", "home office", "brasil",
                          "são paulo", "rio de janeiro", "belo horizonte"]:
                if termo in snippet.lower():
                    location = termo.capitalize()
                    break

            # Extrai data do snippet (evita acessar a página individualmente)
            posted_at = extract_date_from_snippet(snippet)

            seen_links.add(link)
            novos += 1
            all_jobs.append({
                "title":     title,
                "company":   r.get("displayed_link", "").split("›")[0].strip(),
                "location":  location,
                "link":      link,
                "site_name": "serpapi.google",
                "posted_at": posted_at,  # já preenchido — date_parser vai pular
            })

        print(f"  [SERP] ✅ '{query[:60]}...' → {novos} resultado(s)")

    print(f"\n  [SERP] 📦 Total coletado: {len(all_jobs)} vagas")
    return all_jobs
