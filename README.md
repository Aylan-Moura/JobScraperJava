# ☕ Java Job Scraper

Scraper automatizado de vagas de emprego para desenvolvedores **Java**, com filtros por nível, localidade e data de postagem. Roda via Docker e salva os resultados no PostgreSQL.

---

## 📋 O que ele busca

| Filtro | Valores aceitos |
|---|---|
| **Stack** | Java, Spring Boot, Quarkus, Maven, Hibernate |
| **Nível** | Estágio, Junior, Senior |
| **Localidade** | Ceará (presencial/híbrido) + Brasil (somente remoto) |
| **Data** | Apenas vagas postadas nos últimos **7 dias** |

Vagas fora do Ceará que não forem remotas são **descartadas automaticamente**.

---

## 🛠️ Tecnologias

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.12 |
| Scraping | `requests` + `BeautifulSoup` |
| Busca inteligente | SerpAPI (Google Search + LinkedIn) |
| Banco de dados | PostgreSQL 15 |
| Cache | Redis 7 |
| Containerização | Docker + Docker Compose V2 |

---

## 📁 Estrutura do Projeto

```
job-scraper/
├── app/
│   ├── main.py           # Ponto de entrada — orquestra todo o fluxo
│   ├── scraper.py        # Download e parsing de HTML (requests)
│   ├── serp_scraper.py   # Busca via SerpAPI (Google + LinkedIn)
│   ├── filters.py        # Filtros de nível, stack, localização e deduplicação
│   ├── date_parser.py    # Verifica data de postagem de cada vaga
│   └── database.py       # Conexão e criação de tabelas no PostgreSQL
├── .env                  # Credenciais do banco e chave da SerpAPI
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## 🚀 Como Usar

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) instalado
- [Docker Compose V2](https://docs.docker.com/compose/install/) (`docker compose` sem hífen)
- Conta na [SerpAPI](https://serpapi.com) (100 buscas/mês grátis)

---

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/job-scraper.git
cd job-scraper
```

### 2. Configure o arquivo `.env`

Abra o arquivo `.env` e preencha com suas credenciais:

```env
POSTGRES_USER=scraper
POSTGRES_PASSWORD=scraper
POSTGRES_DB=jobs
POSTGRES_HOST=db
POSTGRES_PORT=5432
SERPAPI_KEY=sua_chave_aqui
```

> Para obter sua chave SerpAPI: acesse [serpapi.com](https://serpapi.com) → faça login → copie a **API Key** do dashboard.

### 3. Rode o scraper

**Primeira vez ou após mudanças no código:**
```bash
docker compose up --build
```

**Nas demais execuções:**
```bash
docker compose up
```

> ⚠️ Use `docker compose` (sem hífen) — o `docker-compose` com hífen é a versão v1 e é incompatível com Python 3.12.

---

## 📊 Exemplo de Saída

```
── SITES COM REQUESTS ──────────────────────────────────────────────
🔍 Acessando: vagas.com.br ...
   12 vagas brutas encontradas
🔍 Acessando: infojobs.com.br ...
   8 vagas brutas encontradas

── SERPAPI (GOOGLE SEARCH + LINKEDIN) ──────────────────────────────
  [SERP] ✅ 'site:vagas.com.br "java junior" "Fortaleza"...' → 4 resultado(s)
  [SERP] ✅ 'site:linkedin.com/jobs "java junior" "Fortaleza"...' → 3 resultado(s)
  [SERP] 📦 Total coletado: 31 vagas

📊 Após filtros (nível / stack / localização / duplicatas):
   📍 Ceará   — Junior: 5 | Estágio: 2 | Senior: 1
   🌐 Remoto  — Junior: 8 | Estágio: 3 | Senior: 4

======================================================================
  📍  VAGAS NO CEARÁ — 8 vaga(s)
======================================================================

  ── 🎓 ESTÁGIO (2) ─────────────────────────────────────────────
  [1] Estágio em Desenvolvimento Java
       Empresa  : Empresa XYZ
       Local    : Fortaleza
       Postada  : 08/03/2026
       Site     : vagas.com.br
       Link     : https://...

  ── 👨‍💻 JUNIOR (5) ─────────────────────────────────────────────
  [1] Desenvolvedor Java Junior
       Empresa  : Empresa ABC
       Local    : Fortaleza
       Postada  : 09/03/2026
       Site     : serpapi.google
       Link     : https://linkedin.com/jobs/view/123456

======================================================================
  🌐  VAGAS REMOTAS NO BRASIL — 15 vaga(s)
======================================================================
...

======================================================================
  📋  TODAS AS VAGAS ENCONTRADAS — 23 vaga(s)
======================================================================
...
```

---

## ⚙️ Configurações

### Alterar o limite de dias das vagas

Em `app/date_parser.py`:
```python
MAX_DAYS_OLD = 7  # altere para o número de dias desejado
```

### Adicionar novos sites de busca direta

Em `app/main.py`, adicione URLs na lista `SITES`:
```python
SITES = [
    "https://www.vagas.com.br/vagas-de-desenvolvedor-java-junior",
    "https://novo-site.com.br/vagas-java",  # adicione aqui
]
```

### Adicionar novas queries de busca (SerpAPI)

Em `app/serp_scraper.py`, adicione na lista `SERP_QUERIES`:
```python
SERP_QUERIES = [
    # ...queries existentes...
    'site:catho.com.br "java junior" "Fortaleza" OR "Ceará"',  # novo
]
```

### Adicionar novas tecnologias Java ao filtro

Em `app/filters.py`:
```python
TECH_KEYWORDS = [
    "java", "spring", "spring boot", "quarkus",
    "micronaut",  # adicione aqui
]
```

---

## 🗄️ Banco de Dados

As vagas são salvas automaticamente na tabela `jobs` do PostgreSQL:

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL | Chave primária |
| `title` | TEXT | Título da vaga |
| `company` | TEXT | Empresa |
| `location` | TEXT | Localização |
| `link` | TEXT | URL da vaga (único) |
| `site_name` | TEXT | Fonte (ex: `vagas.com.br`) |
| `category` | TEXT | `ceara_junior`, `remote_senior`, etc. |
| `posted_at` | TIMESTAMP | Data de postagem |
| `created_at` | TIMESTAMP | Data em que o scraper encontrou |

Para acessar o banco diretamente:
```bash
docker exec -it job_scraper_db psql -U scraper -d jobs
```

```sql
-- Ver todas as vagas salvas
SELECT title, company, location, category, posted_at FROM jobs ORDER BY posted_at DESC;

-- Filtrar só vagas do Ceará
SELECT * FROM jobs WHERE category LIKE 'ceara_%';

-- Filtrar só vagas remotas junior
SELECT * FROM jobs WHERE category = 'remote_junior';
```

---

## ⚠️ Problemas Conhecidos

| Problema | Causa | Solução |
|---|---|---|
| `Conflict. container name already in use` | Container antigo ainda existe | `docker rm -f job_scraper_db job_scraper_redis && docker compose up` |
| `docker-compose: No module named 'distutils'` | Versão antiga do compose | Usar `docker compose` (sem hífen) |
| SerpAPI retorna 0 resultados | Chave inválida ou limite atingido | Verificar chave no dashboard da SerpAPI |
| Vagas sem data descartadas | Site bloqueia acesso ao link | Comportamento esperado — garante qualidade |

---

## 💡 Limite de Uso da SerpAPI

O plano gratuito da SerpAPI oferece **100 buscas/mês**.

O scraper usa **23 queries por execução**, então:

| Execuções/mês | Queries gastas |
|---|---|
| 1x | 23 |
| 2x | 46 |
| 4x | 92 |
| 5x+ | ❌ limite excedido |

Para rodar com mais frequência, considere reduzir queries em `serp_scraper.py` ou assinar um [plano pago](https://serpapi.com/pricing).

---

## 📄 Licença

MIT — use, modifique e distribua à vontade.
