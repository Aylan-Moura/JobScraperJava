"""
Módulo responsável por acessar cada vaga individualmente
e extrair a data de postagem da página.
"""

import re
import time
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from scraper import fetch_page

# Limite em dias: vagas postadas há mais que isso são descartadas
MAX_DAYS_OLD = 7


def parse_date_from_page(html: str) -> datetime | None:
    """
    Tenta extrair a data de postagem do HTML da página individual da vaga.
    Suporta:
      - Datas absolutas: "07/03/2026", "2026-03-07", "March 7, 2026"
      - Datas relativas: "há 3 dias", "2 days ago", "posted 5 days ago"
      - Texto padrão de portais BR/EN
    """
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now()

    # Seletores comuns de data nos portais
    date_selectors = [
        # LinkedIn
        {"name": "span", "class_": lambda c: c and "posted-time-ago" in " ".join(c)},
        {"name": "time"},
        # Indeed
        {"name": "span", "class_": lambda c: c and "date" in " ".join(c)},
        # Gupy / portais BR
        {"name": "span", "class_": lambda c: c and "published" in " ".join(c)},
        {"name": "p",    "class_": lambda c: c and "date" in " ".join(c)},
        # Genérico: qualquer elemento com datetime attr
    ]

    candidates = []

    # 1) Tenta <time datetime="...">
    for time_el in soup.find_all("time"):
        dt_attr = time_el.get("datetime", "")
        if dt_attr:
            parsed = _try_parse_absolute(dt_attr)
            if parsed:
                return parsed
        candidates.append(time_el.get_text(strip=True))

    # 2) Tenta seletores específicos
    for sel in date_selectors:
        tag = sel.pop("name")
        for el in soup.find_all(tag, **sel):
            candidates.append(el.get_text(strip=True))

    # 3) Tenta interpretar os textos encontrados
    for text in candidates:
        result = _try_parse_relative(text, now) or _try_parse_absolute(text)
        if result:
            return result

    # 4) Fallback: busca regex em todo o texto da página
    full_text = soup.get_text(" ", strip=True)
    result = _try_parse_relative(full_text, now) or _try_parse_absolute(full_text)
    return result


def _try_parse_relative(text: str, now: datetime) -> datetime | None:
    """Converte textos como 'há 3 dias' ou '2 days ago' em datetime."""
    text = text.lower()

    # Padrões em português
    pt_patterns = [
        (r"h[aá]\s+(\d+)\s+dia",    "days"),
        (r"h[aá]\s+(\d+)\s+hora",   "hours"),
        (r"h[aá]\s+(\d+)\s+semana", "weeks"),
        (r"h[aá]\s+(\d+)\s+m[eê]s", "months"),
        (r"(\d+)\s+dia[s]?\s+atr",  "days"),
        (r"hoje",                    "today"),
        (r"ontem",                   "yesterday"),
    ]

    # Padrões em inglês
    en_patterns = [
        (r"(\d+)\s+day[s]?\s+ago",    "days"),
        (r"(\d+)\s+hour[s]?\s+ago",   "hours"),
        (r"(\d+)\s+week[s]?\s+ago",   "weeks"),
        (r"(\d+)\s+month[s]?\s+ago",  "months"),
        (r"posted\s+(\d+)\s+day",     "days"),
        (r"just\s+posted|today",       "today"),
        (r"yesterday",                 "yesterday"),
    ]

    for pattern, unit in pt_patterns + en_patterns:
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


def _try_parse_absolute(text: str) -> datetime | None:
    """Tenta converter formatos de data absoluta em datetime."""
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d de %B de %Y",
    ]
    text = text.strip()[:30]  # evita strings gigantes
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def is_within_max_days(posted_at: datetime | None) -> bool:
    """Retorna True apenas se a vaga foi postada dentro do limite de dias.
    Vagas sem data são DESCARTADAS (comportamento seguro).
    """
    if posted_at is None:
        return False  # sem data → descarta
    return (datetime.now() - posted_at).days <= MAX_DAYS_OLD


def enrich_jobs_with_date(jobs: list, delay: float = 1.5) -> list:
    """
    Acessa cada vaga individualmente para capturar a data de postagem.
    Retorna apenas as vagas dentro do limite de MAX_DAYS_OLD dias.
    
    :param jobs:  lista de vagas já filtradas por cargo/localização
    :param delay: espera entre requisições para não sobrecarregar o servidor
    """
    enriched = []
    total = len(jobs)

    print(f"\n📅 Verificando data de postagem em {total} vaga(s)...")

    for i, job in enumerate(jobs, 1):
        link = job.get("link", "")
        print(f"   [{i}/{total}] {job['title'][:50]}...", end=" ", flush=True)

        # Vaga já tem data extraída (ex: via SerpAPI snippet) — só valida prazo
        if job.get("posted_at") is not None:
            posted_at = job["posted_at"]
            if is_within_max_days(posted_at):
                date_str = posted_at.strftime("%d/%m/%Y")
                print(f"✅ {date_str} (snippet)")
                enriched.append(job)
            else:
                date_str = posted_at.strftime("%d/%m/%Y")
                print(f"❌ antiga ({date_str})")
            continue

        if not link or link == job.get("site_name", ""):
            print("⏭  sem link individual — descartada")
            continue  # descarta sem link

        html = fetch_page(link)
        if not html:
            print("⚠  erro ao acessar — descartada")
            continue  # descarta se não conseguiu acessar

        posted_at = parse_date_from_page(html)

        if is_within_max_days(posted_at):
            date_str = posted_at.strftime("%d/%m/%Y") if posted_at else "data não encontrada"
            print(f"✅ {date_str}")
            enriched.append({**job, "posted_at": posted_at})
        else:
            date_str = posted_at.strftime("%d/%m/%Y") if posted_at else "?"
            print(f"❌ antiga ({date_str})")

        # Pausa entre requisições
        time.sleep(delay + random.uniform(0, 0.5))

    return enriched
