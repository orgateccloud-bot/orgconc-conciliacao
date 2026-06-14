from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.core import config as _config
from api.core.rate_limit import limiter
from api.db import refresh_tokens as refresh_repo
from api.db import usuarios as usuarios_repo
from api.db.models import Org
from api.schemas import (
    CriarOrgPayload,
    CriarUsuarioPayload,
    LoginPayload,
    ResetSenhaPayload,
    TrocarSenhaPayload,
)
from api.services.audit import gravar_audit_independente
from api.services.auth import (
    REFRESH_TTL_DAYS,
    TokenPayload,
    current_user,
    decodificar_token,
    emitir_token,
    gerar_refresh_token,
    hash_refresh_token,
    hash_senha,
    require_role,
    revogar_jti,
    verificar_senha,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_DUMMY_HASH = hash_senha("__orgconc_dummy_timing_constant_2026__")

_COOKIE_NAME = "orgconc_token"
_REFRESH_COOKIE_NAME = "orgconc_refresh"
_COOKIE_TTL = int(os.environ.get("ORGCONC_JWT_TTL_MIN", "120")) * 60
_REFRESH_COOKIE_TTL = REFRESH_TTL_DAYS * 24 * 3600
_IS_HTTPS = os.environ.get("ORGCONC_ENV", "").strip().lower() in ("production", "prod") or \
            os.environ.get("ORGCONC_HTTPS_ENABLED", "").strip().lower() in ("1", "true", "yes")


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_IS_HTTPS,
        samesite="strict",
        path="/",
        max_age=_COOKIE_TTL,
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    # path="/auth": o refresh só é enviado para os endpoints /auth/*.
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_IS_HTTPS,
        samesite="strict",
        path="/auth",
        max_age=_REFRESH_COOKIE_TTL,
    )


def _access_token_da_request(request: Request) -> str | None:
    """Extrai o access token (JWT) da request: header Bearer ou cookie."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip() or None
    return request.cookies.get(_COOKIE_NAME)


def _revogar_access_atual(request: Request) -> None:
    """Adiciona o `jti` do access token atual a denylist (#9). Best-effort:
    token ausente/invalido/expirado e ignorado (logout segue idempotente)."""
    tok = _access_token_da_request(request)
    if not tok:
        return
    try:
        payload = decodificar_token(tok)
    except HTTPException:
        # Token ja invalido/expirado/revogado: nada a revogar.
        return
    if payload.jti:
        revogar_jti(payload.jti, payload.exp)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _client_ua(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _e_uuid(s: str) -> bool:
    """True se a string é um UUID — distingue sessão de usuário do DB (sub=uuid)
    de sessão legada/env-admin (sub=email)."""
    try:
        uuid.UUID(str(s))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


async def _emitir_refresh_persistido(
    sub: str,
    request: Request,
    *,
    role: str = "user",
    cliente_id: str | None = None,
) -> str:
    """Cria e persiste um refresh token. Retorna o token plain (vai p/ o cliente).

    role/cliente_id sao persistidos para que /auth/refresh reemita o access token
    preservando a identidade real da sessao (sem escalar para admin).
    """
    token_plain = gerar_refresh_token()
    expira = datetime.now(timezone.utc) + timedelta(days=REFRESH_TTL_DAYS)
    async with _config.SessionLocal() as db:
        await refresh_repo.criar(
            db,
            sub=sub,
            role=role,
            cliente_id=cliente_id,
            token_hash=hash_refresh_token(token_plain),
            expira_em=expira,
            ip=_client_ip(request),
            user_agent=_client_ua(request),
        )
    return token_plain


@router.post("/login")
@limiter.limit("10/minute")
async def auth_login(request: Request, response: Response, payload: LoginPayload):
    """Login por usuário (multi-org) com fallback para o admin por env.

    Tenta primeiro um usuário no banco (token leva `org_id` + `role` da org). Se
    não houver banco ou usuário, cai no ORGCONC_ADMIN_EMAIL/_SENHA_HASH (admin
    sem org) — bootstrap. Um único verificar_senha (timing constante).
    """
    email_norm = payload.email.strip().lower()
    admin_email = os.environ.get("ORGCONC_ADMIN_EMAIL", "").strip().lower()
    admin_hash = os.environ.get("ORGCONC_ADMIN_SENHA_HASH", "").strip()
    db_ok = _config.DB_DISPONIVEL and _config.SessionLocal is not None
    env_admin_ok = bool(admin_email and admin_hash)

    if not db_ok and not env_admin_ok:
        raise HTTPException(
            status_code=503,
            detail="Auth nao configurada — defina ORGCONC_ADMIN_EMAIL e ORGCONC_ADMIN_SENHA_HASH no .env (ou crie usuarios)",
        )

    user = None
    if db_ok:
        async with _config.SessionLocal() as db:
            user = await usuarios_repo.buscar_por_email(db, email_norm)

    # Hash candidato + identidade — um ÚNICO verificar_senha p/ não vazar
    # existência de email por timing.
    if user is not None:
        candidate_hash, identidade = user.senha_hash, "db"
    elif env_admin_ok and email_norm == admin_email:
        candidate_hash, identidade = admin_hash, "env"
    else:
        candidate_hash, identidade = _DUMMY_HASH, None

    senha_ok = verificar_senha(payload.senha, candidate_hash)
    if identidade is None or not senha_ok:
        raise HTTPException(status_code=401, detail="Credenciais invalidas")

    if identidade == "db":
        sub, email, role, org_id = str(user.id), user.email, user.role, str(user.org_id)
        superadmin = False
    else:  # env admin — superadmin sem org (bootstrap): leitura cross-org
        sub, email, role, org_id = admin_email, admin_email, "admin", None
        superadmin = True

    token = emitir_token(sub=sub, email=email, role=role, org_id=org_id, superadmin=superadmin)
    _set_auth_cookie(response, token)

    if identidade == "db":
        async with _config.SessionLocal() as db:
            await usuarios_repo.registrar_login(db, user.id)

    resp_body = {"access_token": token, "token_type": "bearer"}
    # Refresh token: só emite se há DB para persistir (revogação server-side).
    if db_ok:
        refresh_plain = await _emitir_refresh_persistido(
            sub, request, role=role, cliente_id=None
        )
        _set_refresh_cookie(response, refresh_plain)
        resp_body["refresh_emitted"] = True
        resp_body["refresh_ttl_days"] = REFRESH_TTL_DAYS
    else:
        resp_body["refresh_emitted"] = False

    await gravar_audit_independente(
        action="login.success",
        resource_type="auth",
        resource_id=sub,
        payload={"role": role, "org_id": org_id},
        actor=TokenPayload(sub=sub, email=email, role=role, org_id=org_id),
    )
    return resp_body


@router.post("/refresh")
@limiter.limit("30/minute")
async def auth_refresh(request: Request, response: Response):
    """Rotaciona o refresh token e emite um novo access token.

    Anti-replay com reuse-detection (RFC 6819): o refresh antigo é revogado e
    aponta para o novo. Apresentar um refresh JÁ ROTACIONADO fora da janela de
    graça (corrida benigna de tabs paralelas) indica cookie comprometido —
    todas as sessões do usuário são revogadas antes do 401.
    """
    if not _config.DB_DISPONIVEL or _config.SessionLocal is None:
        raise HTTPException(503, "Refresh indisponivel — banco nao configurado")
    rt_plain = request.cookies.get(_REFRESH_COOKIE_NAME)
    if not rt_plain:
        raise HTTPException(401, "Refresh token ausente")

    rt_hash = hash_refresh_token(rt_plain)
    async with _config.SessionLocal() as db:
        # #22 — rotacao atomica: lock de linha (FOR UPDATE) + criar/revogar num
        # unico commit. Requests simultaneos com o mesmo refresh serializam no
        # lock; o 2o ja ve o token consumido (None) e cai na reuse-detection.
        row = await refresh_repo.buscar_ativo_por_hash(db, rt_hash, for_update=True)
        if not row:
            # Reuse-detection: token rotacionado sendo reapresentado?
            antigo = await refresh_repo.buscar_por_hash(db, rt_hash)
            if (
                antigo is not None
                and antigo.revogado_em is not None
                and antigo.substituido_por is not None
                and (datetime.now(timezone.utc) - antigo.revogado_em).total_seconds() > 10
            ):
                n = await refresh_repo.revogar_todos_do_sub(db, antigo.sub)
                await gravar_audit_independente(
                    action="auth.refresh_reuse_detected",
                    resource_type="auth",
                    resource_id=str(antigo.id),
                    payload={"sessoes_revogadas": n},
                    actor=TokenPayload(sub=antigo.sub, role=antigo.role or "user"),
                )
            raise HTTPException(401, "Refresh invalido ou expirado")
        sub = row.sub
        # Preserva a identidade real da sessao — NUNCA reemitir admin fixo.
        role = row.role or "user"
        cliente_id = row.cliente_id
        email = sub
        org_id = None
        superadmin = False
        # Multi-org: se o sub é um usuário do banco, re-deriva org/role/email
        # atuais (pega mudança de role/org desde a emissão). Usuário desativado
        # ou removido → buscar_por_id devolve None: barra a rotação.
        u = await usuarios_repo.buscar_por_id(db, sub)
        if u is not None:
            org_id, role, email, cliente_id = str(u.org_id), u.role, u.email, None
        elif _e_uuid(sub):
            raise HTTPException(401, "Usuario inativo ou inexistente")
        else:
            # Sessão legada/env-admin (sub=email). O env-admin só reganha
            # superadmin se o admin-por-env AINDA está ATIVO (#24): exige
            # ORGCONC_ADMIN_EMAIL E ORGCONC_ADMIN_SENHA_HASH presentes. Se o
            # admin-env foi desativado (env removido), a sessão continua válida
            # mas SEM superadmin — não reescala um admin que não existe mais.
            admin_email = os.environ.get("ORGCONC_ADMIN_EMAIL", "").strip().lower()
            admin_hash = os.environ.get("ORGCONC_ADMIN_SENHA_HASH", "").strip()
            env_admin_ativo = bool(admin_email and admin_hash)
            superadmin = env_admin_ativo and sub.strip().lower() == admin_email
        old_id = row.id
        novo_plain = gerar_refresh_token()
        novo_row = await refresh_repo.criar(
            db,
            sub=sub,
            role=role,
            cliente_id=cliente_id,
            token_hash=hash_refresh_token(novo_plain),
            expira_em=datetime.now(timezone.utc) + timedelta(days=REFRESH_TTL_DAYS),
            ip=_client_ip(request),
            user_agent=_client_ua(request),
            commit=False,
        )
        await refresh_repo.revogar(db, old_id, substituido_por=novo_row.id, commit=False)
        await db.commit()

    novo_access = emitir_token(sub=sub, email=email, role=role, cliente_id=cliente_id,
                               org_id=org_id, superadmin=superadmin)
    _set_auth_cookie(response, novo_access)
    _set_refresh_cookie(response, novo_plain)
    return {"access_token": novo_access, "token_type": "bearer", "refresh_emitted": True}


@router.post("/logout")
async def auth_logout(request: Request, response: Response):
    """Revoga o refresh atual (se houver) e limpa cookies. Idempotente.

    #9 — tambem coloca o `jti` do access token atual na denylist, encerrando a
    janela em que o access (TTL ~120min) ainda valeria apos o logout.
    """
    rt_plain = request.cookies.get(_REFRESH_COOKIE_NAME)
    if rt_plain and _config.DB_DISPONIVEL and _config.SessionLocal is not None:
        async with _config.SessionLocal() as db:
            await refresh_repo.revogar_por_hash(db, hash_refresh_token(rt_plain))
    _revogar_access_atual(request)
    response.delete_cookie(key=_COOKIE_NAME, path="/", samesite="strict")
    response.delete_cookie(key=_REFRESH_COOKIE_NAME, path="/auth", samesite="strict")
    return {"detail": "Sessao encerrada"}


@router.post("/logout-all")
async def auth_logout_all(
    request: Request, response: Response, user: TokenPayload = Depends(current_user)
):
    """Logout global — revoga TODOS os refresh tokens ativos do usuario.

    #9 — revoga tambem o `jti` do access atual via denylist. (Os demais access
    tokens emitidos para o mesmo sub expiram pelo TTL curto; a renovacao ja esta
    barrada pela revogacao de todos os refresh.)
    """
    revogados = 0
    if _config.DB_DISPONIVEL and _config.SessionLocal is not None:
        async with _config.SessionLocal() as db:
            revogados = await refresh_repo.revogar_todos_do_sub(db, user.sub)
    _revogar_access_atual(request)
    response.delete_cookie(key=_COOKIE_NAME, path="/", samesite="strict")
    response.delete_cookie(key=_REFRESH_COOKIE_NAME, path="/auth", samesite="strict")
    return {"detail": "Sessoes encerradas", "revogados": revogados}


@router.get("/me")
async def auth_me(user: TokenPayload = Depends(current_user)):
    return {"sub": user.sub, "email": user.email, "role": user.role, "org_id": user.org_id}


# ── Gestão de organizações e usuários (bootstrap; admin/service) ──────────────


def _db_obrigatorio() -> None:
    if not (_config.DB_DISPONIVEL and _config.SessionLocal is not None):
        raise HTTPException(503, "Banco nao configurado")


@router.post("/orgs")
async def auth_criar_org(
    payload: CriarOrgPayload,
    user: TokenPayload = Depends(require_role("admin", "service")),
):
    """Cria uma organização (tenant). Bootstrap por admin/service."""
    _db_obrigatorio()
    plano = payload.plano or "basico"
    async with _config.SessionLocal() as db:
        org = Org(nome=payload.nome, cnpj=payload.cnpj, plano=plano)
        db.add(org)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, "CNPJ ja cadastrado")
        await db.refresh(org)
        org_id = str(org.id)
    await gravar_audit_independente(
        action="org.create", resource_type="org", resource_id=org_id,
        payload={"nome": payload.nome}, actor=user,
    )
    return {"id": org_id, "nome": payload.nome, "plano": plano}


@router.get("/orgs")
async def auth_listar_orgs(
    user: TokenPayload = Depends(require_role("admin", "service")),
):
    """Lista as organizações (tenants). Bootstrap por admin/service."""
    _db_obrigatorio()
    async with _config.SessionLocal() as db:
        orgs = (await db.execute(select(Org).order_by(Org.criado_em))).scalars().all()
        return [
            {
                "id": str(o.id),
                "nome": o.nome,
                "cnpj": o.cnpj,
                "plano": o.plano,
                "ativo": o.ativo,
                "criado_em": o.criado_em.isoformat() if o.criado_em else None,
            }
            for o in orgs
        ]


@router.post("/usuarios")
async def auth_criar_usuario(
    payload: CriarUsuarioPayload,
    user: TokenPayload = Depends(require_role("admin", "service")),
):
    """Cria um usuário numa organização. Bootstrap por admin/service."""
    _db_obrigatorio()
    try:
        org_uuid = uuid.UUID(payload.org_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(400, "org_id invalido")
    async with _config.SessionLocal() as db:
        if await db.get(Org, org_uuid) is None:
            raise HTTPException(404, "Organizacao nao encontrada")
        try:
            novo = await usuarios_repo.criar(
                db,
                email=payload.email,
                senha_hash=hash_senha(payload.senha),
                org_id=org_uuid,
                role=payload.role or "user",
                nome=payload.nome,
            )
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, "Email ja cadastrado")
        uid, uemail, urole = str(novo.id), novo.email, novo.role
    await gravar_audit_independente(
        action="usuario.create", resource_type="usuario", resource_id=uid,
        payload={"email": uemail, "org_id": payload.org_id, "role": urole}, actor=user,
    )
    return {"id": uid, "email": uemail, "org_id": payload.org_id, "role": urole}


@router.post("/senha")
@limiter.limit("10/minute")
async def auth_trocar_senha(
    request: Request,
    payload: TrocarSenhaPayload,
    user: TokenPayload = Depends(current_user),
):
    """Troca a própria senha (exige a senha atual). Só p/ usuários do banco.

    Ao trocar, revoga todos os refresh tokens do usuário (re-login nas outras
    sessões). O admin por env (sub=email) usa senha por variável de ambiente —
    não dá para trocar aqui.
    """
    _db_obrigatorio()
    if not _e_uuid(user.sub):
        raise HTTPException(400, "Troca de senha indisponivel para esta conta (admin por env)")
    async with _config.SessionLocal() as db:
        u = await usuarios_repo.buscar_por_id(db, user.sub)
        if u is None:
            raise HTTPException(401, "Usuario inativo ou inexistente")
        if not verificar_senha(payload.senha_atual, u.senha_hash):
            raise HTTPException(401, "Senha atual incorreta")
        await usuarios_repo.atualizar_senha(db, u.id, hash_senha(payload.senha_nova))
        await refresh_repo.revogar_todos_do_sub(db, str(u.id))
    # #9 — revoga o access atual via denylist (os demais expiram pelo TTL curto;
    # a renovacao ja esta barrada pela revogacao de todos os refresh acima).
    _revogar_access_atual(request)
    await gravar_audit_independente(
        action="usuario.senha.trocar", resource_type="usuario", resource_id=user.sub,
        payload={"self": True}, actor=user,
    )
    return {"detail": "Senha alterada. Faça login novamente nas outras sessões."}


@router.post("/usuarios/{usuario_id}/senha")
async def auth_reset_senha(
    usuario_id: str,
    payload: ResetSenhaPayload,
    user: TokenPayload = Depends(require_role("admin", "service")),
):
    """Reset de senha de um usuário por admin/service. Revoga os refresh dele."""
    _db_obrigatorio()
    try:
        uid = uuid.UUID(usuario_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(400, "usuario_id invalido")
    async with _config.SessionLocal() as db:
        n = await usuarios_repo.atualizar_senha(db, uid, hash_senha(payload.senha_nova))
        if not n:
            raise HTTPException(404, "Usuario nao encontrado")
        await refresh_repo.revogar_todos_do_sub(db, str(uid))
    await gravar_audit_independente(
        action="usuario.senha.reset", resource_type="usuario", resource_id=usuario_id,
        payload={"by": user.sub}, actor=user,
    )
    return {"detail": "Senha redefinida; sessões do usuário revogadas."}


@router.get("/usuarios")
async def auth_listar_usuarios(
    org_id: str,
    user: TokenPayload = Depends(require_role("admin", "service")),
):
    """Lista usuários de uma organização (sem o hash de senha)."""
    _db_obrigatorio()
    try:
        org_uuid = uuid.UUID(org_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(400, "org_id invalido")
    async with _config.SessionLocal() as db:
        us = await usuarios_repo.listar_por_org(db, org_uuid)
        return [
            {
                "id": str(u.id),
                "email": u.email,
                "nome": u.nome,
                "role": u.role,
                "ativo": u.ativo,
                "criado_em": u.criado_em.isoformat() if u.criado_em else None,
            }
            for u in us
        ]


@router.post("/hash", include_in_schema=False)
async def auth_hash_helper(payload: dict, _user: TokenPayload = Depends(current_user)):
    if _config._IS_PROD:
        raise HTTPException(status_code=404, detail="Indisponivel")
    if _user.role == "anonymous":
        raise HTTPException(status_code=401, detail="Token Bearer obrigatorio para /hash")
    senha = payload.get("senha", "")
    if not senha or len(senha) < 8:
        raise HTTPException(status_code=400, detail="Senha minima de 8 chars")
    return {"hash": hash_senha(senha)}
