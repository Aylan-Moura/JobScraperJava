# ── Níveis aceitos ────────────────────────────────────────────────────
LEVEL_KEYWORDS = {
    "estagio": [
        "estágio", "estagio", "estag", "intern", "internship",
    ],
    "junior": [
        "junior", "júnior", "jr", "jr.",
    ],
    "senior": [
        "senior", "sênior", "sr", "sr.",
    ],
}

# ── Stack: apenas Java ────────────────────────────────────────────────
TECH_KEYWORDS = [
    "java", "spring", "spring boot", "quarkus", "maven", "hibernate",
    "jakarta", "jvm",
]

# ── Termos que identificam vagas do Ceará ─────────────────────────────
CEARA_TERMS = [
    "ceará", "ceara", "fortaleza", "sobral", "juazeiro do norte",
    "juazeiro", "caucaia", "maracanaú", "maracanau", "crato",
    "iguatu", "quixadá", "quixada", "pacatuba",
    "ce -", "- ce", "(ce)", "ce,", ", ce", "/ce",
]

# ── Termos que identificam vagas remotas ──────────────────────────────
REMOTE_TERMS = [
    "remoto", "remote", "home office", "homeoffice",
    "100% remoto", "trabalho remoto", "totalmente remoto",
    "fully remote", "teletrabalho", "work from home",
    "anywhere in brazil", "todo o brasil",
]

# ── Termos que confirmam Brasil ───────────────────────────────────────
BRAZIL_TERMS = [
    "brasil", "brazil", "são paulo", "sao paulo", "rio de janeiro",
    "belo horizonte", "curitiba", "porto alegre", "fortaleza", "ceará",
    "recife", "salvador", "manaus", "brasília", "brasilia",
    "campinas", "florianópolis", "florianopolis", "goiânia", "goiania",
]

# ── Termos que indicam vaga FORA do Brasil ────────────────────────────
FOREIGN_TERMS = [
    "united states", " usa", "u.s.", "canada", " uk ", "united kingdom",
    "europe", "europa", "germany", "deutschland", "france", "spain",
    "australia", "new zealand", "worldwide", "global",
    "anywhere in the world", "international only", "latam only",
]


def get_level(title: str):
    t = title.lower()
    for label, keywords in LEVEL_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return label
    return None


def matches_java(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in TECH_KEYWORDS)


def matches_job(title: str) -> bool:
    """Vaga válida = tem nível aceito E menciona Java."""
    return get_level(title) is not None and matches_java(title)


def matches_ceara(job: dict) -> bool:
    text = " ".join([
        job.get("title", ""), job.get("location", ""), job.get("link", ""),
    ]).lower()
    return any(term in text for term in CEARA_TERMS)


def matches_remote(job: dict) -> bool:
    text = " ".join([job.get("title", ""), job.get("location", "")]).lower()
    return any(term in text for term in REMOTE_TERMS)


def matches_brazil(job: dict) -> bool:
    text = " ".join([
        job.get("title", ""), job.get("location", ""), job.get("link", ""),
    ]).lower()
    if any(term in text for term in FOREIGN_TERMS):
        return False
    if any(term in text for term in BRAZIL_TERMS):
        return True
    return False  # ambíguo → descarta


def deduplicate(jobs: list) -> list:
    import re
    def normalize(title: str) -> str:
        t = title.lower()
        t = re.sub(r"[^a-záéíóúàãõâêîôûç0-9 ]", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    seen_links, seen_titles, unique = set(), set(), []
    for job in jobs:
        link  = job.get("link", "").strip()
        title = normalize(job.get("title", ""))
        if link and link in seen_links:
            continue
        if title and title in seen_titles:
            continue
        seen_links.add(link)
        seen_titles.add(title)
        unique.append(job)
    return unique


def filter_jobs(jobs: list) -> dict:
    """
    Filtra vagas Java por nível (estágio/junior/senior).
    Aceita: Ceará (presencial/híbrido) OU remoto dentro do Brasil.
    Vagas do Ceará não aparecem duplicadas em remoto.
    """
    ceara, remote = [], []

    for job in jobs:
        title = job.get("title", "")
        if not matches_job(title):
            continue

        job["level"] = get_level(title)
        job["stack"] = "java"

        is_ceara  = matches_ceara(job)
        is_remote = matches_remote(job) and matches_brazil(job)

        # Descarta sem localização identificável
        if not is_ceara and not is_remote:
            continue

        if is_ceara:
            ceara.append(job)
        if is_remote and not is_ceara:
            remote.append(job)

    return {
        "ceara":  deduplicate(ceara),
        "remote": deduplicate(remote),
    }
