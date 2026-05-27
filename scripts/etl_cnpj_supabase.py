"""ETL CNPJ RFB → Supabase/PostgreSQL com asyncpg e pgBouncer-friendly.

Adaptação de `D:\\00_Inbox\\OrgNeural\\etl_cnpj.py` para o Supabase do OrgConc:
- usa o DSN do `.env` (DATABASE_URL) via api.core.config
- usa psycopg2 para COPY FROM (asyncpg não suporta COPY de arquivo grande tão bem)
- aplica o schema cnpj.* idempotente (01_schema.sql do OrgNeural)
- cria índices ao final (02_indices.sql)

Pré-requisitos:
1. Baixar manualmente os ZIPs do mês mais recente em:
   https://www.gov.br/receitafederal/.../dados-publicos-cnpj
2. Descompactar em pasta única (ex: D:\\cnpj_csv\\)
3. Garantir que DATABASE_URL aponta para um Postgres com ~80 GB livres
   (Supabase Free não comporta — usar Pro/Team ou Postgres self-hosted)

Uso:
  python scripts/etl_cnpj_supabase.py --dir D:\\cnpj_csv
  python scripts/etl_cnpj_supabase.py --dir D:\\cnpj_csv --skip-schema  # refresh mensal
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time
from pathlib import Path

import psycopg2  # síncrono é melhor para COPY FROM de arquivos grandes

# Reusa configuração do projeto (.env + DATABASE_URL)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.core.config import _DB_URL  # noqa: E402

ORGNEURAL_DIR = Path(r"D:\00_Inbox\OrgNeural")
SCHEMA_SQL = ORGNEURAL_DIR / "01_schema.sql"
INDEXES_SQL = ORGNEURAL_DIR / "02_indices.sql"

SPEC = [
    ("cnaes",            "CNAECSV",  2,  "cnpj.cnaes"),
    ("municipios",       "MUNICCSV", 2,  "cnpj.municipios"),
    ("naturezas",        "NATJUCSV", 2,  "cnpj.naturezas"),
    ("paises",           "PAISCSV",  2,  "cnpj.paises"),
    ("motivos",          "MOTICSV",  2,  "cnpj.motivos"),
    ("qualificacoes",    "QUALSCSV", 2,  "cnpj.qualificacoes"),
    ("empresas",         "EMPRECSV", 7,  "cnpj.empresas"),
    ("simples",          "SIMPLES",  7,  "cnpj.simples"),
    ("socios",           "SOCIOCSV", 11, "cnpj.socios"),
    ("estabelecimentos", "ESTABELE", 30, "cnpj.estabelecimentos"),
]

TRANSFORM_BASE = {
    "empresas": """
        INSERT INTO cnpj.empresas
        SELECT c1, c2, c3, c4,
               NULLIF(replace(c5, ',', '.'), '')::numeric,
               c6, NULLIF(c7, '')
        FROM {stg};""",
    "estabelecimentos": """
        INSERT INTO cnpj.estabelecimentos
        SELECT c1, c2, c3,
               (lpad(c1,8,'0') || lpad(c2,4,'0') || lpad(c3,2,'0'))::char(14),
               c4, c5, c6, cnpj.to_data(c7), c8, c9, c10, cnpj.to_data(c11),
               c12, c13, c14, c15, c16, c17, c18, c19, c20, c21,
               c22, c23, c24, c25, c26, c27, c28, c29, cnpj.to_data(c30)
        FROM {stg};""",
    "socios": """
        INSERT INTO cnpj.socios
        SELECT c1, c2, c3, c4, c5, cnpj.to_data(c6),
               c7, c8, c9, c10, c11
        FROM {stg};""",
    "simples": """
        INSERT INTO cnpj.simples
        SELECT c1, c2, cnpj.to_data(c3), cnpj.to_data(c4),
               c5, cnpj.to_data(c6), cnpj.to_data(c7)
        FROM {stg};""",
}
for _t in ("cnaes", "municipios", "naturezas", "paises", "motivos", "qualificacoes"):
    TRANSFORM_BASE[_t] = f"INSERT INTO cnpj.{_t} SELECT c1, c2 FROM {{stg}};"


INDICES_DROP = [
    "ux_estab_cnpj", "ix_estab_basico", "ux_empresas_basico", "ux_simples_basico",
    "ix_socios_basico", "ix_socios_doc", "ix_socios_nome",
    "ux_cnaes_cod", "ux_municipios_cod", "ux_naturezas_cod",
    "ux_paises_cod", "ux_motivos_cod", "ux_qualificacoes_cod",
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _sync_dsn(url: str) -> str:
    """Converte DSN async (postgresql+asyncpg://) para sync (postgresql://)."""
    return url.replace("postgresql+asyncpg://", "postgresql://")


def find_files(directory: str, token: str) -> list[str]:
    hits = []
    for path in sorted(glob.glob(os.path.join(directory, "*"))):
        if os.path.isfile(path) and token in os.path.basename(path).upper():
            hits.append(path)
    return hits


def load_table(conn, directory: str, name: str, token: str, ncols: int, final: str) -> None:
    cur = conn.cursor()
    files = find_files(directory, token)
    if not files:
        log(f"  AVISO: nenhum arquivo '{token}' encontrado -> '{name}' pulada.")
        cur.close()
        return

    stg = f"stg_{name}"
    cols = ", ".join(f"c{i} text" for i in range(1, ncols + 1))
    cur.execute(f"DROP TABLE IF EXISTS {stg};")
    cur.execute(f"CREATE UNLOGGED TABLE {stg} ({cols});")

    t0 = time.time()
    total_bytes = 0
    copy_sql = (f"COPY {stg} FROM STDIN WITH "
                f"(FORMAT csv, DELIMITER ';', QUOTE '\"', ENCODING 'LATIN1')")
    for path in files:
        size = os.path.getsize(path)
        total_bytes += size
        log(f"  COPY {os.path.basename(path)} ({size/1e6:.1f} MB)")
        with open(path, "rb") as f:
            cur.copy_expert(copy_sql, f)

    cur.execute(f"TRUNCATE {final};")
    cur.execute(TRANSFORM_BASE[name].format(stg=stg))
    cur.execute(f"DROP TABLE {stg};")
    conn.commit()

    cur.execute(f"SELECT count(*) FROM {final};")
    rows = cur.fetchone()[0]
    log(f"  OK {name}: {rows:,} linhas, {total_bytes/1e6:.0f} MB, {time.time()-t0:.0f}s")
    cur.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="ETL base CNPJ RFB -> Supabase do OrgConc")
    ap.add_argument("--dir", required=True,
                    help="pasta com os CSV da RFB já descompactados")
    ap.add_argument("--dsn", default=None,
                    help="DSN Postgres alternativo; padrão usa DATABASE_URL do .env")
    ap.add_argument("--skip-schema", action="store_true",
                    help="não aplicar 01_schema.sql (refresh mensal)")
    args = ap.parse_args()

    if not os.path.isdir(args.dir):
        sys.exit(f"ERRO: pasta nao encontrada: {args.dir}")
    if not SCHEMA_SQL.exists() or not INDEXES_SQL.exists():
        sys.exit(
            f"ERRO: nao encontrei {SCHEMA_SQL} / {INDEXES_SQL}. "
            f"Garanta que D:\\00_Inbox\\OrgNeural\\ existe."
        )

    dsn = args.dsn or _DB_URL
    if not dsn:
        sys.exit("ERRO: DATABASE_URL nao configurado (use --dsn ou edite .env)")
    dsn = _sync_dsn(dsn)
    log(f"Conectando em: {dsn.split('@')[-1] if '@' in dsn else dsn}")

    inicio = time.time()
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    if not args.skip_schema:
        log("Aplicando 01_schema.sql")
        cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
        conn.commit()

    log("Removendo indices (recriados ao final, mais rapido)")
    for ix in INDICES_DROP:
        cur.execute(f"DROP INDEX IF EXISTS cnpj.{ix};")
    conn.commit()
    cur.close()

    for name, token, ncols, final in SPEC:
        log(f"Tabela: {name}")
        load_table(conn, args.dir, name, token, ncols, final)

    cur = conn.cursor()
    log("Criando indices (02_indices.sql)")
    cur.execute(INDEXES_SQL.read_text(encoding="utf-8"))
    conn.commit()
    log("ANALYZE")
    conn.set_isolation_level(0)
    for tbl in ("empresas", "estabelecimentos", "socios", "simples"):
        cur.execute(f"ANALYZE cnpj.{tbl};")
    cur.close()
    conn.close()

    elapsed = (time.time() - inicio) / 60
    log(f"CONCLUIDO em {elapsed:.1f} min")
    log("")
    log("A base local agora e usada como FALLBACK quando BrasilAPI falha.")
    log("Para forcar uso da base local, indisponibilize a rede.")


if __name__ == "__main__":
    main()
