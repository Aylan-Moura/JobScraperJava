import psycopg2
import os

def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        database=os.getenv("POSTGRES_DB", "jobs"),
        user=os.getenv("POSTGRES_USER", "scraper"),
        password=os.getenv("POSTGRES_PASSWORD", "scraper"),
        port=os.getenv("POSTGRES_PORT", "5432"),
    )

def create_table():
    conn = get_connection()
    cur = conn.cursor()

    # Cria a tabela se não existir
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id         SERIAL PRIMARY KEY,
            title      TEXT,
            company    TEXT,
            location   TEXT,
            link       TEXT,
            site_name  TEXT,
            category   TEXT,
            posted_at  TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(title, link)
        )
    """)

    # Migration: adiciona colunas novas caso a tabela já existia sem elas
    migrations = [
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS location  TEXT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS category  TEXT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS site_name TEXT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS posted_at TIMESTAMP",
    ]
    for sql in migrations:
        cur.execute(sql)

    conn.commit()
    cur.close()
    conn.close()
