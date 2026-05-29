"""Variaveis de ambiente e flags globais."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

_DB_IMPORTS_OK = False
SessionLocal = None
engine = None
crud_clientes = None
models = None

try:
    from api.db.client import SessionLocal as _SL, engine as _eng
    from api.db import models as _models
    from api.db import clientes as _crud_clientes
    SessionLocal = _SL
    engine = _eng
    models = _models
    crud_clientes = _crud_clientes
    _DB_IMPORTS_OK = True
except ImportError:
    # api.db nao disponivel (asyncpg/sqlalchemy ausentes em ambiente minimo)
    pass

_IS_PROD_ENV = os.environ.get("ORGCONC_ENV", "").strip().lower() in ("production", "prod")
# Alias canonico: codigo deve ler config._IS_PROD (live) para que patches em
# testes (patch("api.core.config._IS_PROD", True)) afetem o comportamento.
_IS_PROD = _IS_PROD_ENV

_cors_raw = os.environ.get("ORGCONC_CORS_ORIGINS", "").strip()
if not _cors_raw:
    if _IS_PROD_ENV:
        raise RuntimeError(
            "ORGCONC_CORS_ORIGINS obrigatorio em producao. "
            "Ex: ORGCONC_CORS_ORIGINS=https://app.orgatec.cloud"
        )
    _cors_raw = "http://127.0.0.1:8765,http://localhost:8765"
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
MAX_UPLOAD_MB = int(os.environ.get("ORGCONC_MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_UPLOAD_TOTAL_MB = int(os.environ.get("ORGCONC_MAX_UPLOAD_TOTAL_MB", "50"))
MAX_UPLOAD_TOTAL_BYTES = MAX_UPLOAD_TOTAL_MB * 1024 * 1024
# Limite de corpo bruto da request (multipart, JSON). Protege contra payloads
# gigantes antes do parsing. Lido live pelo middleware de body-limit.
_MAX_BODY_BYTES = int(os.environ.get("ORGCONC_MAX_BODY_BYTES", str(60 * 1024 * 1024)))
DATA_DIR = Path(os.environ.get("ORGCONC_DATA_DIR", "./data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

if os.environ.get("_ORGCONC_TESTS_DB_SKIP") == "1":
    _DB_URL = ""
else:
    _DB_URL = os.environ.get("DATABASE_URL", "").strip()


def _db_ping_sync(timeout_s: int = 10) -> bool:
    """Verifica conectividade; retry 3x com backoff exponencial."""
    if not _DB_URL or re.search(r"\[.+?\]", _DB_URL):
        return False
    url = _DB_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    import time
    import psycopg2
    for attempt in range(3):
        try:
            with psycopg2.connect(url, connect_timeout=timeout_s) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except (psycopg2.OperationalError, psycopg2.DatabaseError):
            if attempt < 2:
                time.sleep(2 ** attempt)
    return False


# DB_DISPONIVEL e inicializado como False no import-time para nao bloquear startup.
# O ping real e feito em verificar_db_disponivel(), chamada no lifespan do bootstrap.
# Isso evita ate 14s de bloqueio na importacao quando o DB esta offline ou lento.
DB_DISPONIVEL: bool = False

# Modulos que fazem `from api.core.config import DB_DISPONIVEL` capturam o valor
# como snapshot no proprio namespace. Precisamos propagar o resultado do ping
# atualizado para cada um deles apos verificar_db_disponivel() rodar no lifespan.
_DB_DISPONIVEL_CONSUMERS: tuple[str, ...] = (
    "api.main",
    "api.routers.activity",
    "api.routers.ai",
    "api.routers.audit",
    "api.routers.clientes",
    "api.routers.conciliacoes_list",
    "api.routers.health",
    "api.routers.metrics",
    "api.routers.transacoes",
    "api.services.db_persistence",
)


def verificar_db_disponivel() -> bool:
    """Executa o ping real do DB e atualiza a flag global DB_DISPONIVEL.

    Deve ser chamada no startup (lifespan). Modulos que fizeram
    `from api.core.config import DB_DISPONIVEL` recebem o valor propagado
    em seu proprio namespace (mantem compatibilidade com tests que usam
    patch("api.routers.X.DB_DISPONIVEL", ...)).
    """
    global DB_DISPONIVEL
    import sys
    DB_DISPONIVEL = _DB_IMPORTS_OK and bool(_DB_URL) and _db_ping_sync()
    for mod_name in _DB_DISPONIVEL_CONSUMERS:
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "DB_DISPONIVEL"):
            setattr(mod, "DB_DISPONIVEL", DB_DISPONIVEL)
    return DB_DISPONIVEL

_LOG_JSON = os.environ.get("ORGCONC_LOG_JSON", "true").strip().lower() not in ("0", "false", "no")
_LOG_LEVEL = os.environ.get("ORGCONC_LOG_LEVEL", "INFO").strip()

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = ROOT_DIR / "static"
REACT_DIST = ROOT_DIR / "orgconc-react" / "dist"

SYSTEM_PROMPT = (
    "Voce e um agente especializado em conciliacao bancaria para escritorios "
    "contabeis brasileiros. Recebe extratos (OFX/CSV) e/ou razao contabil, "
    "cruza por data/valor/descricao, identifica conciliados, divergencias, "
    "duplicidades e nao conciliados, e gera relatorio em portugues com resumo "
    "executivo, achados criticos, classificacao contabil e plano de acao."
)

_MODELOS_MULTI = [
    ("claude-opus-4-7", "Opus 4.7", "🔵"),
    ("claude-sonnet-4-6", "Sonnet 4.6", "🟢"),
    ("claude-haiku-4-5-20251001", "Haiku 4.5", "🟡"),
]

_MODELOS_VALIDOS = {
    "haiku": ("claude-haiku-4-5-20251001", "Haiku 4.5"),
    "sonnet": ("claude-sonnet-4-6", "Sonnet 4.6"),
    "opus": ("claude-opus-4-7", "Opus 4.7"),
}

_PLANOS_VALIDOS = {"basico", "pro", "enterprise"}

log = logging.getLogger("orgconc")


def _validate_production_env() -> None:
    """Levanta RuntimeError se variaveis obrigatorias estiverem ausentes em producao."""
    if not _IS_PROD_ENV:
        return
    missing = []
    if len(os.environ.get("ORGCONC_JWT_SECRET", "").strip()) < 32:
        missing.append("ORGCONC_JWT_SECRET (>= 32 chars — gere com: openssl rand -hex 32)")
    if not os.environ.get("ORGCONC_ADMIN_EMAIL", "").strip():
        missing.append("ORGCONC_ADMIN_EMAIL")
    if not os.environ.get("ORGCONC_ADMIN_SENHA_HASH", "").strip():
        missing.append("ORGCONC_ADMIN_SENHA_HASH")
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        raise RuntimeError(
            "Variaveis obrigatorias em producao ausentes ou fracas:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

_validate_production_env()
