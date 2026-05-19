"""
API de Conciliacao Bancaria.

Endpoints:
- GET  /              - info do servico
- GET  /health        - healthcheck
- POST /conciliar/ofx - recebe 1 ou 2 arquivos OFX e devolve relatorio em Markdown
- POST /conciliar/csv - recebe CSV extrato + CSV razao contabil e devolve relatorio

Execucao:
    uvicorn api.main:app --reload --port 8765
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import secrets
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from anthropic import Anthropic, APIStatusError
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from markdown import markdown as md_to_html
import contextlib
from pydantic import BaseModel
from sqlalchemy import text as sql_text

# Parsers extraidos para api/parsers/
from api.parsers import (
    _parse_ofx,
    _parse_xml,
    _parse_pdf,
    _parse_arquivo,
    _classificar,
    _detectar_anomalias,
    _top_categorias_e_contrapartes,
    _fmt_csv,
)
# Gerador de relatorio local extraido para api/services/
from api.services.relatorio_local import _conciliacao_local
# Geracao XLSX extraida para api/services/
from api.services.excel import _gerar_xlsx

# --- Config via .env (deve rodar ANTES dos imports de banco) ---
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

# Imports de banco (opcionais — ativos somente se DATABASE_URL estiver configurado)
_DB_IMPORTS_OK = False
try:
    from api.db.client import SessionLocal, engine
    from api.db import models
    from api.db import clientes as crud_clientes
    _DB_IMPORTS_OK = True
except Exception:
    pass

AUTH_TOKEN = os.environ.get("ORGCONC_AUTH_TOKEN", "").strip()
CORS_ORIGINS = [
    o.strip() for o in os.environ.get(
        "ORGCONC_CORS_ORIGINS",
        "http://127.0.0.1:8765,http://localhost:8765",
    ).split(",") if o.strip()
]
MAX_UPLOAD_MB = int(os.environ.get("ORGCONC_MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
# Soma agregada de todos os arquivos por requisicao (anti-OOM)
MAX_UPLOAD_TOTAL_MB = int(os.environ.get("ORGCONC_MAX_UPLOAD_TOTAL_MB", "50"))
MAX_UPLOAD_TOTAL_BYTES = MAX_UPLOAD_TOTAL_MB * 1024 * 1024
DATA_DIR = Path(os.environ.get("ORGCONC_DATA_DIR", "./data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

_DB_URL = os.environ.get("DATABASE_URL", "").strip()
DB_DISPONIVEL = _DB_IMPORTS_OK and bool(_DB_URL) and not re.search(r"\[.+?\]", _DB_URL)

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("orgconc")

# --- Rate limiter ---
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

SYSTEM_PROMPT = (
    "Voce e um agente especializado em conciliacao bancaria para escritorios "
    "contabeis brasileiros. Recebe extratos (OFX/CSV) e/ou razao contabil, "
    "cruza por data/valor/descricao, identifica conciliados, divergencias, "
    "duplicidades e nao conciliados, e gera relatorio em portugues com resumo "
    "executivo, achados criticos, classificacao contabil e plano de acao."
)

@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY nao configurada — /conciliar/ofx (sem simular) nao funcionara")
    if DB_DISPONIVEL:
        log.info("Banco configurado: %s", _DB_URL.split("@")[-1] if "@" in _DB_URL else "ok")
    else:
        log.info("Banco nao configurado — persistencia JSON local ativa")
    yield
    if DB_DISPONIVEL and _DB_IMPORTS_OK:
        await engine.dispose()


app = FastAPI(
    title="ORGATEC · Conciliacao Bancaria API",
    description="Cruza extratos OFX/PDF/XML contra razao contabil. Gera HTML/XLSX/PDF.",
    version="0.3.0",
    lifespan=_lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS else ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

_CSP = (
    "default-src 'self'; "
    "script-src 'self' cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
    "font-src 'self' fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "upgrade-insecure-requests"
)

class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next) -> StarletteResponse:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

app.add_middleware(_SecurityHeadersMiddleware)


from api.services.auth import (
    auth_optional,
    current_user,
    decodificar_token,
    emitir_token,
    hash_senha,
    verificar_senha,
    TokenPayload,
)


def auth(authorization: Optional[str] = Header(None)) -> None:
    """Wrapper retrocompativel: aceita JWT OU token legacy.

    Se ORGCONC_AUTH_TOKEN nao estiver configurado, libera (modo dev).
    """
    if not AUTH_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token Bearer ausente")
    token = authorization.split(" ", 1)[1].strip()
    # 1. Tenta token legacy (igual ao AUTH_TOKEN)
    if secrets.compare_digest(token, AUTH_TOKEN):
        return
    # 2. Tenta JWT — levanta 401 se invalido
    decodificar_token(token)


# ── Modelos Pydantic ──────────────────────────────────────────────────────

def _validar_cnpj(cnpj: str) -> bool:
    digits = re.sub(r"\D", "", cnpj)
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    def _calc(d, pesos):
        s = sum(int(d[i]) * pesos[i] for i in range(len(pesos)))
        r = s % 11
        return 0 if r < 2 else 11 - r
    p1 = [5,4,3,2,9,8,7,6,5,4,3,2]
    p2 = [6,5,4,3,2,9,8,7,6,5,4,3,2]
    return int(digits[12]) == _calc(digits, p1) and int(digits[13]) == _calc(digits, p2)


_PLANOS_VALIDOS = {"basico", "pro", "enterprise"}


class ClienteCreate(BaseModel):
    nome: str
    cnpj: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    plano: str = "basico"

    def model_post_init(self, __context) -> None:
        if self.cnpj:
            self.cnpj = re.sub(r"\D", "", self.cnpj)  # normaliza: remove máscara
            if not _validar_cnpj(self.cnpj):
                raise ValueError(f"CNPJ inválido: {self.cnpj}")
        if self.plano not in _PLANOS_VALIDOS:
            raise ValueError(f"Plano inválido: {self.plano}. Use: {sorted(_PLANOS_VALIDOS)}")


class ClienteUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    plano: Optional[str] = None
    ativo: Optional[bool] = None

    def model_post_init(self, __context) -> None:
        if self.plano is not None and self.plano not in _PLANOS_VALIDOS:
            raise ValueError(f"Plano inválido: {self.plano}. Use: {sorted(_PLANOS_VALIDOS)}")


# ── Persistência no banco ─────────────────────────────────────────────────

async def _salvar_no_banco(
    report_id: str,
    extratos: list[dict],
    anomalias: list[dict],
    modo: str,
    cliente_id: Optional[str] = None,
) -> dict:
    """Persiste conciliacao no banco. Retorna dict com status: ok|skip|error."""
    if not DB_DISPONIVEL:
        return {"status": "skip", "motivo": "db_indisponivel"}
    import uuid as _uuid
    from datetime import date
    try:
        total_cred = sum(t["valor"] for e in extratos for t in e["transacoes"] if t["valor"] > 0)
        total_deb  = sum(t["valor"] for e in extratos for t in e["transacoes"] if t["valor"] < 0)
        datas = sorted({t["data"] for e in extratos for t in e["transacoes"] if t.get("data")})
        cid = _uuid.UUID(cliente_id) if cliente_id else None
        async with SessionLocal() as db:
            async with db.begin():
                conc = models.Conciliacao(
                    cliente_id=cid,
                    report_id=report_id,
                    modo=modo,
                    total_transacoes=sum(e["qtd"] for e in extratos),
                    total_anomalias=len(anomalias),
                    valor_total_credito=total_cred,
                    valor_total_debito=total_deb,
                    periodo_inicio=date.fromisoformat(datas[0]) if datas else None,
                    periodo_fim=date.fromisoformat(datas[-1]) if datas else None,
                )
                db.add(conc)
                await db.flush()
                anomalias_set = {
                    (a.get("conta", ""), round(abs(a.get("valor", 0)), 2))
                    for a in anomalias
                }
                txs = [
                    models.Transacao(
                        conciliacao_id=conc.id,
                        cliente_id=cid,
                        data_lancamento=date.fromisoformat(t["data"]) if t.get("data") else date.today(),
                        valor=t["valor"],
                        memo=t.get("memo"),
                        categoria=_classificar(t.get("memo", ""), t.get("nome", "")),
                        banco=e.get("conta"),
                        tipo=t.get("tipo"),
                        eh_anomalia=(e.get("conta", ""), round(abs(t["valor"]), 2)) in anomalias_set,
                    )
                    for e in extratos for t in e["transacoes"]
                ]
                db.add_all(txs)
            log.info("Conciliacao %s salva no banco (%d transacoes)", report_id, len(txs))
        return {"status": "ok", "transacoes_persistidas": len(txs)}
    except Exception as exc:
        log.exception("Falha ao salvar no banco (conciliacao %s) — JSON preservado", report_id)
        return {"status": "error", "erro": type(exc).__name__, "mensagem": str(exc)[:200]}


async def read_limited(up: UploadFile, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """Le upload com limite de tamanho. Aborta se exceder."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await up.read(1024 * 256)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Arquivo {up.filename} excede {MAX_UPLOAD_MB} MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)

_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(_static_dir), html=True), name="ui")

# Jinja2 templates (relatorios HTML/PDF)
from jinja2 import Environment, FileSystemLoader, select_autoescape
_templates_dir = Path(__file__).resolve().parent / "templates"
_jinja = Environment(
    loader=FileSystemLoader(str(_templates_dir)),
    autoescape=select_autoescape(["html"]),
)

# Logo embutida (base64) para HTML standalone e PDF
import base64
_LOGO_PATH = _static_dir / "logo.png"
_LOGO_B64 = ""
_LOGO_DATA_URI = ""
if _LOGO_PATH.exists():
    _LOGO_B64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()
    _LOGO_DATA_URI = f"data:image/png;base64,{_LOGO_B64}"


def _get_client() -> Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY nao configurada no servidor",
        )
    return Anthropic(api_key=key)


# Modelos usados no modo multi-modelo (ordem: capacidade decrescente)
_MODELOS_MULTI = [
    ("claude-opus-4-7",           "Opus 4.7",   "🔵"),
    ("claude-sonnet-4-6",         "Sonnet 4.6", "🟢"),
    ("claude-haiku-4-5-20251001", "Haiku 4.5",  "🟡"),
]


async def _chamar_modelo_async(
    api_key: str,
    prompt: str,
    model_id: str,
    label: str,
    max_tokens: int,
) -> dict:
    """Chama um modelo Claude em thread executor (SDK síncrono → async seguro)."""
    import asyncio
    loop = asyncio.get_event_loop()

    def _call():
        c = Anthropic(api_key=api_key)
        resp = c.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "texto": "\n".join(b.text for b in resp.content if b.type == "text"),
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }

    try:
        res = await loop.run_in_executor(None, _call)
    except APIStatusError as e:
        body = getattr(e, "body", None) or {}
        msg = (body.get("error") or {}).get("message") or str(e)
        log.warning("Erro no modelo %s: %s", model_id, msg)
        res = {"texto": "", "input_tokens": 0, "output_tokens": 0, "erro": msg}
    else:
        res["erro"] = None

    res.update({"modelo": model_id, "label": label})
    return res


async def _sintetizar_consenso(
    api_key: str,
    resultados: list[dict],
    max_tokens: int,
) -> tuple[str, float]:
    """Usa Sonnet 4.6 como juiz para sintetizar N relatórios em consenso.

    Retorna (relatorio_consolidado, score_consenso 0.0-1.0).
    """
    validos = [r for r in resultados if not r.get("erro") and r["texto"]]
    if not validos:
        return "Nenhum modelo produziu resultado válido.", 0.0
    if len(validos) == 1:
        return validos[0]["texto"], 0.5

    secoes = "\n\n".join(
        f"### Análise — {r['label']}\n{r['texto']}"
        for r in validos
    )
    prompt_juiz = (
        f"Você recebeu {len(validos)} análises independentes do mesmo extrato bancário, "
        "geradas por modelos Claude diferentes. Produza um RELATÓRIO FINAL consolidado em Markdown:\n\n"
        "1. Primeira linha: `## Índice de Consenso: XX/100` — calcule baseado na concordância entre modelos\n"
        "2. ✅ Achados confirmados por ≥ 2 modelos → alta confiança\n"
        "3. ⚠️ Pontos divergentes → requerem revisão humana\n"
        "4. Seções obrigatórias: Resumo Executivo · Anomalias · Classificações Contábeis · Plano de Ação\n"
        "5. Seção final: **Convergências e Divergências entre Modelos** — liste o que cada modelo encontrou "
        "de diferente e o grau de concordância por tópico\n\n"
        f"---\n\n{secoes}"
    )
    res = await _chamar_modelo_async(api_key, prompt_juiz, "claude-sonnet-4-6", "Síntese", max_tokens)
    texto = res["texto"] or validos[0]["texto"]

    m = re.search(r"[Íi]ndice\s+de\s+[Cc]onsenso[:\s]+(\d+)", texto)
    score = int(m.group(1)) / 100.0 if m else (len(validos) / 3 * 0.8)
    return texto, round(min(max(score, 0.0), 1.0), 3)


def _salvar_dataset(extratos: list[dict], anomalias: list[dict], relatorio: str) -> str:
    """Persiste o dataset em disco (./data/{rid}.json) e retorna o ID."""
    import uuid
    rid = uuid.uuid4().hex[:12]
    path = DATA_DIR / f"{rid}.json"
    payload = {
        "extratos": extratos,
        "anomalias": anomalias,
        "relatorio": relatorio,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    # Limpa datasets antigos: mantem so os 50 mais recentes
    existing = sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in existing[50:]:
        try: old.unlink()
        except OSError: pass
    log.info("Dataset salvo: %s (%d transacoes, %d anomalias)", rid,
             sum(e["qtd"] for e in extratos), len(anomalias))
    return rid


def _carregar_dataset(rid: str) -> dict:
    """Carrega dataset persistido."""
    # Sanitiza o ID para evitar path traversal
    if not re.fullmatch(r"[a-f0-9]{12}", rid):
        raise HTTPException(status_code=400, detail="ID invalido")
    path = DATA_DIR / f"{rid}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado ou expirado")
    return json.loads(path.read_text(encoding="utf-8"))


def _render_html(relatorio_md: str) -> str:
    """Renderiza relatorio Markdown como HTML standalone via template Jinja2."""
    from datetime import datetime
    body = md_to_html(relatorio_md, extensions=["tables", "fenced_code"])
    return _jinja.get_template("relatorio.html").render(
        body=body,
        agora=datetime.now().strftime("%d/%m/%Y %H:%M"),
        logo_data_uri=_LOGO_DATA_URI,
    )


@app.get("/app", include_in_schema=False)
def frontend():
    """Serve o dashboard frontend."""
    html_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    if not html_path.exists():
        raise HTTPException(404, "Frontend não encontrado")
    return FileResponse(str(html_path), media_type="text/html")


@app.get("/animate-demo", include_in_schema=False)
def animate_demo():
    """Serve a página de demo do animate.css."""
    html_path = Path(__file__).resolve().parent.parent / "frontend" / "animate-demo.html"
    if not html_path.exists():
        raise HTTPException(404, "Demo não encontrado")
    return FileResponse(str(html_path), media_type="text/html")


@app.get("/")
def root():
    return {
        "service": "Conciliacao Bancaria API",
        "version": "0.3.0",
        "endpoints": [
            "/health", "/docs",
            "/conciliar/ofx",
            "/export/html/{report_id}", "/export/xlsx/{report_id}", "/export/pdf/{report_id}",
            "/clientes", "/clientes/{id}",
            "/auth/login", "/auth/me",
            "/logo-base64",
        ],
    }


@app.get("/health")
async def health():
    db_status = "nao_configurado"
    if DB_DISPONIVEL:
        try:
            async with SessionLocal() as db:
                await db.execute(sql_text("SELECT 1"))
            db_status = "ok"
        except Exception:
            db_status = "erro"
    return {
        "status": "ok",
        "versao": "0.3.0",
        "api_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "banco_dados": db_status,
    }


# ── Auth (JWT) ────────────────────────────────────────────────────────────

class LoginPayload(BaseModel):
    email: str
    senha: str


@app.post("/auth/login", tags=["auth"])
@limiter.limit("10/minute")
async def auth_login(request: Request, payload: LoginPayload):
    """Emite JWT a partir de email + senha.

    Para o MVP atual, valida contra ORGCONC_ADMIN_EMAIL + ORGCONC_ADMIN_SENHA_HASH
    do .env (single-user). Quando houver tabela users, valida contra BD.
    """
    admin_email = os.environ.get("ORGCONC_ADMIN_EMAIL", "").strip().lower()
    admin_hash = os.environ.get("ORGCONC_ADMIN_SENHA_HASH", "").strip()

    if not admin_email or not admin_hash:
        raise HTTPException(
            status_code=503,
            detail="Auth nao configurada — defina ORGCONC_ADMIN_EMAIL e ORGCONC_ADMIN_SENHA_HASH no .env",
        )

    if payload.email.strip().lower() != admin_email:
        # Mesma mensagem para email errado e senha errada (evita user enumeration)
        raise HTTPException(status_code=401, detail="Credenciais invalidas")

    if not verificar_senha(payload.senha, admin_hash):
        raise HTTPException(status_code=401, detail="Credenciais invalidas")

    token = emitir_token(sub=admin_email, email=admin_email, role="admin")
    return {"access_token": token, "token_type": "bearer"}


@app.get("/auth/me", tags=["auth"])
async def auth_me(user: TokenPayload = Depends(current_user)):
    """Retorna info do usuario autenticado (debug/UI)."""
    return {"sub": user.sub, "email": user.email, "role": user.role}


@app.post("/auth/hash", tags=["auth"], include_in_schema=False)
async def auth_hash_helper(payload: dict):
    """Helper de DEV: gera bcrypt hash de uma senha (uso: setup inicial).

    Disponivel apenas quando ORGCONC_AUTH_TOKEN esta vazio (modo dev).
    """
    if AUTH_TOKEN:
        raise HTTPException(status_code=404, detail="Indisponivel")
    senha = payload.get("senha", "")
    if not senha or len(senha) < 8:
        raise HTTPException(status_code=400, detail="Senha minima de 8 chars")
    return {"hash": hash_senha(senha)}


# ── Clientes ──────────────────────────────────────────────────────────────

@app.post("/clientes", dependencies=[Depends(auth)], status_code=201, tags=["clientes"])
@limiter.limit("20/minute")
async def criar_cliente(request: Request, payload: ClienteCreate):
    """Cadastra um novo cliente."""
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado — adicione DATABASE_URL ao .env")
    from sqlalchemy.exc import IntegrityError
    try:
        async with SessionLocal() as db:
            cliente = await crud_clientes.criar_cliente(
                db, nome=payload.nome, cnpj=payload.cnpj,
                email=payload.email, telefone=payload.telefone, plano=payload.plano,
            )
    except IntegrityError:
        raise HTTPException(409, "CNPJ já cadastrado")
    return {
        "id": str(cliente.id), "nome": cliente.nome, "cnpj": cliente.cnpj,
        "email": cliente.email, "plano": cliente.plano,
        "criado_em": cliente.criado_em.isoformat(),
    }


@app.get("/clientes", dependencies=[Depends(auth)], tags=["clientes"])
@limiter.limit("30/minute")
async def listar_clientes(request: Request, apenas_ativos: bool = True):
    """Lista todos os clientes."""
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    async with SessionLocal() as db:
        clientes = await crud_clientes.listar_clientes(db, apenas_ativos=apenas_ativos)
    return [
        {"id": str(c.id), "nome": c.nome, "cnpj": c.cnpj, "email": c.email,
         "plano": c.plano, "ativo": c.ativo}
        for c in clientes
    ]


@app.get("/clientes/{cliente_id}", dependencies=[Depends(auth)], tags=["clientes"])
@limiter.limit("30/minute")
async def buscar_cliente(request: Request, cliente_id: str):
    """Busca um cliente pelo ID."""
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    import uuid as _uuid
    try:
        cid = _uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "ID invalido")
    async with SessionLocal() as db:
        cliente = await crud_clientes.buscar_cliente(db, cid)
    if not cliente:
        raise HTTPException(404, "Cliente nao encontrado")
    return {
        "id": str(cliente.id), "nome": cliente.nome, "cnpj": cliente.cnpj,
        "email": cliente.email, "telefone": cliente.telefone,
        "plano": cliente.plano, "ativo": cliente.ativo,
        "criado_em": cliente.criado_em.isoformat(),
    }


@app.patch("/clientes/{cliente_id}", dependencies=[Depends(auth)], tags=["clientes"])
@limiter.limit("20/minute")
async def atualizar_cliente(request: Request, cliente_id: str, payload: ClienteUpdate):
    """Atualiza dados de um cliente."""
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    import uuid as _uuid
    try:
        cid = _uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "ID invalido")
    campos = {k: v for k, v in payload.model_dump().items() if v is not None}
    async with SessionLocal() as db:
        cliente = await crud_clientes.atualizar_cliente(db, cid, **campos)
    if not cliente:
        raise HTTPException(404, "Cliente nao encontrado")
    return {"id": str(cliente.id), "nome": cliente.nome, "plano": cliente.plano, "ativo": cliente.ativo}


# ── Conciliação ───────────────────────────────────────────────────────────

_MODELOS_VALIDOS = {
    "haiku":  ("claude-haiku-4-5-20251001", "Haiku 4.5"),
    "sonnet": ("claude-sonnet-4-6",         "Sonnet 4.6"),
    "opus":   ("claude-opus-4-7",           "Opus 4.7"),
}


@app.post("/conciliar/ofx", dependencies=[Depends(auth)])
@limiter.limit("20/minute")
async def conciliar_ofx(
    request: Request,
    arquivos: List[UploadFile] = File(..., description="1 a 50 arquivos (.ofx, .pdf ou .xml)"),
    max_tokens: int = 16000,
    simular: bool = False,
    multi_modelo: bool = False,
    modelo: str = "sonnet",
    cliente_id: Optional[str] = None,
):
    """Cruza ate 50 extratos bancarios (OFX, PDF ou XML).

    Modos:
    - simular=true  → análise heurística local, sem LLM
    - multi_modelo=true → 3 modelos Claude em paralelo + síntese de consenso
    - modelo=haiku → Haiku 4.5 (rápido e barato, ideal para triagem de grande volume)
    - modelo=sonnet (padrão) → Sonnet 4.6 (qualidade recomendada)
    - modelo=opus → Opus 4.7 (máxima profundidade)
    """
    if modelo not in _MODELOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"modelo invalido: {modelo}. Use: {sorted(_MODELOS_VALIDOS.keys())}",
        )
    if not (1 <= len(arquivos) <= 50):
        raise HTTPException(status_code=400, detail="Envie entre 1 e 50 arquivos")

    extratos_parsed = []
    total_lido = 0
    for up in arquivos:
        content = await read_limited(up)
        total_lido += len(content)
        if total_lido > MAX_UPLOAD_TOTAL_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Soma dos uploads excede {MAX_UPLOAD_TOTAL_MB} MB",
            )
        try:
            txs = _parse_arquivo(content, up.filename)
        except HTTPException:
            raise
        except Exception as e:
            log.exception("Falha parseando %s", up.filename)
            raise HTTPException(
                status_code=400,
                detail=f"Falha ao parsear {up.filename}: {type(e).__name__}",
            )
        if not txs:
            raise HTTPException(
                status_code=400,
                detail=f"Nao foi possivel extrair transacoes de {up.filename}",
            )
        extratos_parsed.append({
            "arquivo": up.filename,
            "conta": txs[0]["conta"],
            "qtd": len(txs),
            "transacoes": txs,
        })

    if simular:
        anomalias = _detectar_anomalias(extratos_parsed)
        relatorio = _conciliacao_local(extratos_parsed, anomalias)
        rid = _salvar_dataset(extratos_parsed, anomalias, relatorio)
        db_status = await _salvar_no_banco(rid, extratos_parsed, anomalias, "simulacao", cliente_id)
        return JSONResponse({
            "modo": "simulacao_local",
            "report_id": rid,
            "extratos": [
                {"arquivo": e["arquivo"], "conta": e["conta"], "qtd": e["qtd"]}
                for e in extratos_parsed
            ],
            "anomalias": anomalias,
            "relatorio_md": relatorio,
            "relatorio_html": _render_html(relatorio),
            "persistencia": db_status,
        })

    # ── Monta prompt comum ─────────────────────────────────────────────────
    blocos = [
        f"=== {e['conta']} ({e['arquivo']}) ===\n"
        f"Total: {e['qtd']} transacoes\n{_fmt_csv(e['transacoes'])}"
        for e in extratos_parsed
    ]
    n_contas = len(extratos_parsed)
    prompt = (
        f"Analise os {n_contas} extrato(s) bancario(s) abaixo. "
        "Identifique transferencias entre contas proprias (INTERCREDIS/TED entre as mesmas contas), "
        "duplicidades, transacoes atipicas e pre-classifique para lancamento contabil. "
        "Consolide o fluxo de caixa considerando todas as contas em conjunto. "
        "Gere relatorio em portugues em Markdown.\n\n"
        + "\n\n".join(blocos)
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY") or ""
    if not api_key:
        raise HTTPException(500, "ANTHROPIC_API_KEY nao configurada no servidor")

    # ── Modo multi-modelo: 3 modelos em paralelo + síntese ────────────────
    if multi_modelo:
        import asyncio as _aio
        tokens_por_modelo = max(4000, max_tokens // 2)

        tarefas = [
            _chamar_modelo_async(api_key, prompt, mid, label, tokens_por_modelo)
            for mid, label, _ in _MODELOS_MULTI
        ]
        resultados = list(await _aio.gather(*tarefas))

        relatorio_consolidado, score_consenso = await _sintetizar_consenso(
            api_key, resultados, max_tokens
        )
        anomalias = _detectar_anomalias(extratos_parsed)
        rid = _salvar_dataset(extratos_parsed, anomalias, relatorio_consolidado)
        db_status = await _salvar_no_banco(rid, extratos_parsed, anomalias, "multi_modelo", cliente_id)

        return JSONResponse({
            "modo": "multi_modelo",
            "report_id": rid,
            "score_consenso": score_consenso,
            "modelos": [
                {
                    "modelo": r["modelo"],
                    "label": r["label"],
                    "input_tokens": r.get("input_tokens", 0),
                    "output_tokens": r.get("output_tokens", 0),
                    "erro": r.get("erro"),
                }
                for r in resultados
            ],
            "extratos": [
                {"arquivo": e["arquivo"], "conta": e["conta"], "qtd": e["qtd"]}
                for e in extratos_parsed
            ],
            "anomalias": anomalias,
            "relatorio_md": relatorio_consolidado,
            "relatorio_html": _render_html(relatorio_consolidado),
            "relatorios_individuais": {
                r["label"]: r["texto"] for r in resultados if r["texto"]
            },
            "persistencia": db_status,
        })

    # ── Modo single model (haiku|sonnet|opus) ────────────────────────────
    model_id, model_label = _MODELOS_VALIDOS[modelo]
    log.info("Conciliacao single-model: %s (%s)", modelo, model_id)
    client = _get_client()
    try:
        resp = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIStatusError as e:
        body = getattr(e, "body", None) or {}
        msg = (body.get("error") or {}).get("message") or str(e)
        if "credit balance" in msg.lower():
            friendly = ("Saldo de creditos Anthropic esgotado. "
                        "Recarregue em https://platform.claude.com/settings/billing "
                        "ou use ?simular=true para gerar relatorio local.")
        elif "rate" in msg.lower() and "limit" in msg.lower():
            friendly = "Rate limit da Anthropic atingido. Aguarde alguns segundos."
        else:
            friendly = msg
        log.warning("Anthropic API error %s: %s", e.status_code, msg)
        raise HTTPException(status_code=e.status_code, detail={"anthropic_error": friendly})
    relatorio = "\n".join(b.text for b in resp.content if b.type == "text")
    anomalias = _detectar_anomalias(extratos_parsed)
    rid = _salvar_dataset(extratos_parsed, anomalias, relatorio)
    db_status = await _salvar_no_banco(rid, extratos_parsed, anomalias, "llm", cliente_id)

    return JSONResponse({
        "modo": "claude_llm",
        "modelo": modelo,
        "modelo_id": model_id,
        "modelo_label": model_label,
        "report_id": rid,
        "extratos": [
            {"arquivo": e["arquivo"], "conta": e["conta"], "qtd": e["qtd"]}
            for e in extratos_parsed
        ],
        "anomalias": anomalias,
        "usage": {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
        "stop_reason": resp.stop_reason,
        "relatorio_md": relatorio,
        "relatorio_html": _render_html(relatorio),
        "persistencia": db_status,
    })


@app.get("/logo-base64")
def logo_base64():
    """Devolve a logo como data URI (usado pelo frontend para PDF)."""
    return {"data_uri": _LOGO_DATA_URI}


def _render_pdf_html(relatorio_md: str, anomalias: list, extratos: list, report_id: str) -> str:
    """Renderiza HTML print-optimized do relatorio via Jinja2."""
    from datetime import datetime
    body = md_to_html(relatorio_md, extensions=["tables", "fenced_code"])
    total_tx   = sum(e.get("qtd", 0) for e in extratos)
    total_cred = sum(t["valor"] for e in extratos for t in e.get("transacoes", []) if t["valor"] > 0)
    total_deb  = sum(t["valor"] for e in extratos for t in e.get("transacoes", []) if t["valor"] < 0)
    n_crit   = sum(1 for a in anomalias if a.get("severidade") == "critico")
    n_alerta = sum(1 for a in anomalias if a.get("severidade") == "alerta")
    n_atenc  = sum(1 for a in anomalias if a.get("severidade") == "atencao")
    return _jinja.get_template("relatorio_pdf.html").render(
        report_id=report_id,
        agora=datetime.now().strftime("%d/%m/%Y %H:%M"),
        body=body,
        anomalias=anomalias,
        n_anom=len(anomalias),
        n_crit=n_crit, n_alerta=n_alerta, n_atenc=n_atenc,
        total_tx=total_tx,
        total_cred=total_cred,
        total_deb_abs=abs(total_deb),
        n_contas=len(extratos),
        logo_data_uri=_LOGO_DATA_URI,
    )


@app.get("/export/html/{rid}", dependencies=[Depends(auth)])
def export_html(rid: str):
    """Baixa o relatorio renderizado em HTML standalone."""
    ds = _carregar_dataset(rid)
    html = _render_html(ds["relatorio"])
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="conciliacao_{rid}.html"'},
    )


@app.get("/export/xlsx/{rid}", dependencies=[Depends(auth)])
def export_xlsx(rid: str):
    """Baixa o dataset em XLSX (3 abas: Resumo, Transacoes, Anomalias)."""
    ds = _carregar_dataset(rid)
    blob = _gerar_xlsx(ds["extratos"], ds["anomalias"])
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="conciliacao_{rid}.xlsx"'},
    )


@app.get("/export/pdf/{rid}", dependencies=[Depends(auth)])
def export_pdf(rid: str, html: bool = False):
    """Baixa relatorio em PDF (weasyprint server-side). Use ?html=true para receber HTML imprimivel."""
    ds = _carregar_dataset(rid)
    html_content = _render_pdf_html(ds["relatorio"], ds["anomalias"], ds["extratos"], rid)

    if html:
        return Response(
            content=html_content,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="conciliacao_{rid}.html"'},
        )

    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html_content, base_url=None).write_pdf()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="conciliacao_{rid}.pdf"'},
        )
    except Exception as exc:
        log.warning("weasyprint falhou (%s) — retornando HTML imprimivel", exc)
        return Response(
            content=html_content,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="conciliacao_{rid}.html"'},
        )


@app.post("/conciliar/csv", dependencies=[Depends(auth)])
@limiter.limit("20/minute")
async def conciliar_csv(
    request: Request,
    extrato: UploadFile = File(..., description="CSV do extrato bancario"),
    razao: UploadFile = File(..., description="CSV do razao contabil"),
    max_tokens: int = 16000,
):
    """Cruza extrato bancario CSV contra razao contabil CSV."""
    # Limita tamanho de upload via read_limited (mesmo guard do /conciliar/ofx)
    extrato_bytes = await read_limited(extrato)
    razao_bytes = await read_limited(razao)
    extrato_text = extrato_bytes.decode("utf-8", errors="ignore")
    razao_text = razao_bytes.decode("utf-8", errors="ignore")

    prompt = (
        "Realize a conciliacao bancaria entre o extrato e o razao contabil "
        "abaixo. Liste conciliados, divergencias, duplicidades e pendencias.\n\n"
        f"=== EXTRATO BANCARIO ({extrato.filename}) ===\n{extrato_text}\n\n"
        f"=== RAZAO CONTABIL ({razao.filename}) ===\n{razao_text}"
    )

    client = _get_client()
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIStatusError as e:
        body = getattr(e, "body", None) or {}
        msg = (body.get("error") or {}).get("message") or str(e)
        raise HTTPException(status_code=e.status_code, detail={"anthropic_error": msg})
    relatorio = "\n".join(b.text for b in resp.content if b.type == "text")

    return JSONResponse({
        "extrato": extrato.filename,
        "razao": razao.filename,
        "usage": {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
        "stop_reason": resp.stop_reason,
        "relatorio_md": relatorio,
    })
