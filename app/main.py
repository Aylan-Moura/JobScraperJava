import os
import sys
from urllib.parse import urlparse
from dotenv import load_dotenv
from scraper import fetch_page, parse_jobs
from serp_scraper import fetch_serp_jobs
from filters import filter_jobs, deduplicate
from database import create_table, get_connection
from date_parser import enrich_jobs_with_date, MAX_DAYS_OLD

load_dotenv()

# ─────────────────────────────────────────────────────────────────────
#  Sites com requests (rápido)
# ─────────────────────────────────────────────────────────────────────
SITES = [

    # ── Vagas.com — Java ──────────────────────────────────────────────
    "https://www.vagas.com.br/vagas-de-desenvolvedor-java-junior",
    "https://www.vagas.com.br/vagas-de-desenvolvedor-java-senior",
    "https://www.vagas.com.br/vagas-de-estagio-em-java",
    "https://www.vagas.com.br/vagas-de-desenvolvedor-java",

    # ── InfoJobs — Java ───────────────────────────────────────────────
    "https://www.infojobs.com.br/vagas-de-desenvolvedor-java-junior.aspx",
    "https://www.infojobs.com.br/vagas-de-desenvolvedor-java-senior.aspx",
    "https://www.infojobs.com.br/vagas-de-desenvolvedor-java.aspx",
    "https://www.infojobs.com.br/vagas-de-estagio-em-java.aspx",

    # ── Adzuna — Java ─────────────────────────────────────────────────
    "https://www.adzuna.com.br/search?q=java+junior&w=Brasil",
    "https://www.adzuna.com.br/search?q=java+senior&w=Brasil",
    "https://www.adzuna.com.br/search?q=java+estagio&w=Brasil",
    "https://www.adzuna.com.br/search?q=spring+boot+junior&w=Brasil",
]

def site_name_from_url(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def save_jobs(jobs: list, category: str):
    if not jobs:
        return
    conn = get_connection()
    cur = conn.cursor()
    for job in jobs:
        cur.execute(
            """
            INSERT INTO jobs (title, company, location, link, site_name, category, posted_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                job["title"],
                job.get("company", ""),
                job.get("location", ""),
                job["link"],
                job["site_name"],
                f"{category}_{job.get('level', 'junior')}",
                job.get("posted_at"),
            ),
        )
    conn.commit()
    cur.close()
    conn.close()


STACK_EMOJI = {
    "java": "☕ Java",
}

LEVEL_EMOJI = {
    "estagio": "🎓 ESTÁGIO",
    "junior":  "👨‍💻 JUNIOR",
    "senior":  "🏆 SENIOR",
}


def print_section(title: str, emoji: str, jobs: list):
    print(f"\n{'='*70}")
    print(f"  {emoji}  {title} — {len(jobs)} vaga(s)")
    print(f"{'='*70}")

    if not jobs:
        print("\n  Nenhuma vaga encontrada nesta categoria.\n")
        return

    # Agrupa por nível
    from collections import defaultdict
    grupos = defaultdict(list)
    for job in jobs:
        level = job.get("level", "junior")
        grupos[level].append(job)

    def print_jobs(group):
        for i, job in enumerate(group, 1):
            posted   = job.get("posted_at")
            date_str = posted.strftime("%d/%m/%Y") if posted else "data não encontrada"
            print(f"\n  [{i}] {job['title']}")
            if job.get("company"):
                print(f"       Empresa  : {job['company']}")
            if job.get("location"):
                print(f"       Local    : {job['location']}")
            print(f"       Postada  : {date_str}")
            print(f"       Site     : {job['site_name']}")
            print(f"       Link     : {job['link']}")

    for level in ["estagio", "junior", "senior"]:
        group = grupos.get(level, [])
        if not group:
            continue
        level_label = LEVEL_EMOJI.get(level, level.upper())
        print(f"\n  ── {level_label} ({len(group)}) ─────────────────────────────────")
        print_jobs(group)

    print()


def main():
    try:
        create_table()
        use_db = True
    except Exception as e:
        print(f"[AVISO] Banco indisponível ({e}). Rodando sem persistência.\n")
        use_db = False

    all_jobs = []

    # 1) Coleta com requests (sites normais)
    print("── SITES COM REQUESTS ──────────────────────────────────────────────")
    for url in SITES:
        name = site_name_from_url(url)
        print(f"🔍 Acessando: {name} ...")
        html = fetch_page(url)
        if not html:
            continue
        jobs = parse_jobs(html, base_url=url, site_name=name)
        print(f"   {len(jobs)} vagas brutas encontradas")
        all_jobs.extend(jobs)

    # 2) Coleta via SerpAPI — inclui LinkedIn via Google Search
    print("\n── SERPAPI (GOOGLE SEARCH + LINKEDIN) ──────────────────────────────")
    serp_jobs = fetch_serp_jobs()
    all_jobs.extend(serp_jobs)

    print(f"\n   Total bruto coletado: {len(all_jobs)} vagas")

    # 4) Filtra por nível + tecnologia + localização + deduplicação
    resultado   = filter_jobs(all_jobs)
    ceara_jobs  = resultado["ceara"]
    remote_jobs = resultado["remote"]
    all_filtered = deduplicate(ceara_jobs + remote_jobs)

    ceara_jr  = [j for j in ceara_jobs  if j.get("level") == "junior"]
    ceara_est = [j for j in ceara_jobs  if j.get("level") == "estagio"]
    rem_jr    = [j for j in remote_jobs if j.get("level") == "junior"]
    rem_est   = [j for j in remote_jobs if j.get("level") == "estagio"]

    print(f"\n📊 Após filtros (nível / tecnologia / localização / duplicatas):")
    print(f"   📍 Ceará   — Junior: {len(ceara_jr)} | Estágio: {len(ceara_est)}")
    print(f"   🌐 Remoto  — Junior: {len(rem_jr)}   | Estágio: {len(rem_est)}")
    print(f"   🔗 Links únicos: {len(all_filtered)}")

    # 5) Busca data individualmente
    print(f"\n⏱  Buscando datas (vagas com mais de {MAX_DAYS_OLD} dias serão descartadas)...")
    enriched_map = {
        j["link"]: j
        for j in enrich_jobs_with_date(all_filtered)
    }

    ceara_final  = [enriched_map[j["link"]] for j in ceara_jobs  if j["link"] in enriched_map]
    remote_final = [enriched_map[j["link"]] for j in remote_jobs if j["link"] in enriched_map]

    c_jr  = [j for j in ceara_final  if j.get("level") == "junior"]
    c_est = [j for j in ceara_final  if j.get("level") == "estagio"]
    r_jr  = [j for j in remote_final if j.get("level") == "junior"]
    r_est = [j for j in remote_final if j.get("level") == "estagio"]

    print(f"\n✅ Resultado final (vagas recentes, sem duplicatas):")
    print(f"   📍 Ceará   — Junior: {len(c_jr)} | Estágio: {len(c_est)}")
    print(f"   🌐 Remoto  — Junior: {len(r_jr)}   | Estágio: {len(r_est)}")

    # 6) Salva no banco
    if use_db:
        save_jobs(ceara_final,  "ceara")
        save_jobs(remote_final, "remote")
        print(f"💾 Vagas salvas no banco de dados.")

    # 7) Exibe resultado
    todas_final = deduplicate(ceara_final + remote_final)

    print_section("VAGAS NO CEARÁ", "📍", ceara_final)
    print_section("VAGAS REMOTAS NO BRASIL", "🌐", remote_final)
    print_section("TODAS AS VAGAS ENCONTRADAS", "📋", todas_final)


if __name__ == "__main__":
    main()
