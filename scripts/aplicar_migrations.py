"""Aplica supabase/migrations/_aplicar_005_a_007.sql via psycopg2.

Uso:
    python scripts/aplicar_migrations.py

Le DATABASE_URL do .env. Roda em transacao unica — rollback automatico
se qualquer DDL falhar. Captura e imprime os NOTICEs.
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
import os

import psycopg2
import psycopg2.extensions


ROOT = Path(__file__).resolve().parent.parent
SQL_PATH = ROOT / "supabase" / "migrations" / "_aplicar_005_a_007.sql"


def _normalize_url(url: str) -> str:
    # SQLAlchemy asyncpg -> psycopg2 driver
    url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    url = url.replace("postgres://", "postgresql://", 1)
    return url


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("ERRO: DATABASE_URL nao encontrada no .env", file=sys.stderr)
        return 1

    sql = SQL_PATH.read_text(encoding="utf-8")
    print(f"-> Lendo {SQL_PATH.name} ({len(sql)} bytes)")
    print(f"-> Conectando em {db_url.split('@')[1].split('/')[0]} ...")

    conn = psycopg2.connect(_normalize_url(db_url), connect_timeout=10)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)

    # Coletor de NOTICEs
    notices: list[str] = []
    conn.notices = notices  # type: ignore[assignment]

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("[ok] Migrations aplicadas (COMMIT)")
    except Exception as exc:
        conn.rollback()
        print(f"[erro] FALHA — rollback automatico. Erro:\n  {type(exc).__name__}: {exc}", file=sys.stderr)
        # Imprime notices coletados ate o erro
        for n in notices:
            print(f"  [NOTICE] {n.strip()}", file=sys.stderr)
        return 2
    finally:
        conn.close()

    print()
    print("-" * 60)
    print("NOTICEs do Postgres:")
    print("-" * 60)
    for n in notices:
        print(f"  {n.strip()}")

    # Validacao pos-aplicacao
    print()
    print("-" * 60)
    print("Validacao pos-aplicacao:")
    print("-" * 60)
    with psycopg2.connect(_normalize_url(db_url), connect_timeout=10) as c2, c2.cursor() as cur:
        for label, q in [
            ("orgs",                "SELECT COUNT(*) FROM orgs"),
            ("feature_flags",       "SELECT COUNT(*) FROM feature_flags"),
            ("audit_log existe",    "SELECT 1 FROM information_schema.tables WHERE table_name='audit_log'"),
            ("clientes.org_id",     "SELECT 1 FROM information_schema.columns WHERE table_name='clientes' AND column_name='org_id'"),
            ("conciliacoes.org_id", "SELECT 1 FROM information_schema.columns WHERE table_name='conciliacoes' AND column_name='org_id'"),
            ("transacoes.org_id",   "SELECT 1 FROM information_schema.columns WHERE table_name='transacoes' AND column_name='org_id'"),
            ("jobs.org_id",         "SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='org_id'"),
            ("refresh_tokens",      "SELECT 1 FROM information_schema.tables WHERE table_name='refresh_tokens'"),
        ]:
            cur.execute(q)
            r = cur.fetchone()
            val = r[0] if r else "AUSENTE"
            print(f"  {label:25s} = {val}")
    print("-" * 60)
    print("[ok] Tudo pronto. Pode retestar /v1/clientes na API.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
