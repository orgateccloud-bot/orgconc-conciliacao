"""Router /fiscal — Auditoria Fiscal Cruzada (NF-e/CT-e/NFS-e × OFX).

Sprint 1 do Plano de Integração Fiscal. Expõe 4 endpoints:

- POST /fiscal/processar          — Upload ZIPs/XMLs + OFX, processa cascata
- GET  /fiscal/conformidade/{id}  — Score consolidado por cliente
- GET  /fiscal/gap/{id}           — Transações sem NF (gaps)
- GET  /fiscal/risco-tributario/{id} — Estimativa de risco em Lucro Real
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
import uuid
import zipfile
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from api.core.config import (
    DB_DISPONIVEL,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_TOTAL_BYTES,
    MAX_UPLOAD_TOTAL_MB,
    SessionLocal,
)
from api.core.rate_limit import limiter
from api.matchers.auditoria_forense import (
    analisar_auditoria,
    cnpjs_das_transacoes,
    construir_cadastro,
    enriquecer_cadastro,
    resumo_para_dict,
)
from api.matchers.cascata import ler_ofx
from api.matchers.conformidade import calcular_conformidade_fornecedor, classificar_risco
from api.matchers.cruzamento_fiscal import cruzar, resumo
from api.matchers.tributario import (
    estimar_retencoes_nao_recolhidas,
    estimar_risco_tributario_anual,
)
from api.matchers.xml_fiscal import (
    parse_lote_xmls,
)
from api.services.auth import TokenPayload, autorizar_cliente, current_user
from api.services.audit import registrar_audit
from api.services.carta_constatacao import (
    gerar_carta_automatica,
    renderizar_pdf_async,
)
from api.services.fiscal_persistence import (
    listar_conformidade,
    listar_cruzamentos,
    listar_documentos_por_cliente,
    salvar_apuracao,
    salvar_conformidade,
    salvar_cruzamentos,
    salvar_documentos_fiscais,
)
from api.services.storage import read_limited
from api.services import laudo_forense as laudo
from api.services.laudo_async import (
    FORMATOS_LAUDO,
    LaudoEntradaInvalida,
    gerar_laudo_documento,
    sanitize_filename as _sanitize_filename,
)
from api.services import calculadora_cbs_ibs
from api.schemas_cbs_ibs import OperacaoFiscalInput

router = APIRouter(tags=["fiscal"], prefix="/fiscal")
log = logging.getLogger("orgconc.fiscal")

# #37: teto de jobs de laudo simultaneos por org (PENDENTE/EXECUTANDO).
# Evita enfileiramento em massa (DoS na fila) — laudo e tarefa cara (WeasyPrint).
MAX_JOBS_LAUDO_POR_ORG = 5


def _normalizar_empresa_cnpj(empresa_cnpj: str) -> str:
    """#29: valida o CNPJ da entidade auditada antes de virar metadado do laudo.

    Tira a mascara (pontos/barra/hifen) e exige exatamente 14 digitos. Bloqueia
    injecao de HTML/conteudo no laudo (so [0-9]{14} sobrevive). Entrada invalida
    -> HTTP 400. Retorna os 14 digitos normalizados.
    """
    digitos = re.sub(r"\D", "", empresa_cnpj or "")
    if len(digitos) != 14:
        raise HTTPException(400, "empresa_cnpj deve conter 14 dígitos (CNPJ).")
    return digitos


def _separar_arquivos_fiscal(arquivos: list[tuple[str, bytes]]) -> tuple[Optional[bytes], list[tuple[str, bytes]]]:
    """Separa OFX (opcional, 1 arquivo) dos XMLs (lista). Expande ZIPs em memória."""
    ofx_bytes: Optional[bytes] = None
    xmls: list[tuple[str, bytes]] = []

    for filename, conteudo in arquivos:
        nome_lower = filename.lower()
        if nome_lower.endswith(".ofx"):
            if ofx_bytes is not None:
                raise HTTPException(400, "Envie apenas 1 arquivo OFX por requisição.")
            ofx_bytes = conteudo
        elif nome_lower.endswith(".xml"):
            xmls.append((filename, conteudo))
        elif nome_lower.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
                    for member in zf.namelist():
                        lower = member.lower()
                        if lower.endswith(".xml"):
                            with zf.open(member) as fh:
                                xmls.append((member, fh.read()))
                        elif lower.endswith(".ofx"):
                            if ofx_bytes is not None:
                                raise HTTPException(400, "ZIP contém mais de 1 OFX.")
                            with zf.open(member) as fh:
                                ofx_bytes = fh.read()
            except zipfile.BadZipFile:
                raise HTTPException(400, f"Arquivo {filename} não é ZIP válido.")
        else:
            log.warning("fiscal: ignorando arquivo com extensão não suportada: %s", filename)

    if not xmls:
        raise HTTPException(400, "Nenhum XML fornecido (direto ou via ZIP).")

    return ofx_bytes, xmls


@router.post("/processar")
@limiter.limit("5/minute")
async def processar_fiscal(
    request: Request,
    background: BackgroundTasks,
    cliente_id: str = Form(..., description="UUID do cliente"),
    arquivos: List[UploadFile] = File(..., description="ZIP/OFX/XMLs de NF-e + CT-e + (opcional OFX)"),
    user: TokenPayload = Depends(current_user),
):
    """Processa lote de documentos fiscais + (opcional) OFX para cruzamento.

    Aceita:
    - 1+ arquivos XML de NF-e/CT-e/NFS-e OU 1+ ZIPs contendo XMLs
    - (Opcional) 1 OFX para cruzamento doc × pagamento

    Retorna resumo de documentos processados e cruzamentos.
    """
    if not arquivos:
        raise HTTPException(400, "Envie ao menos 1 arquivo.")
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "cliente_id deve ser UUID válido")
    autorizar_cliente(user, cliente_id)
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")

    coletados: list[tuple[str, bytes]] = []
    total = 0
    for up in arquivos:
        conteudo = await read_limited(up, MAX_UPLOAD_BYTES)
        total += len(conteudo)
        if total > MAX_UPLOAD_TOTAL_BYTES:
            raise HTTPException(413, f"Total de uploads excede {MAX_UPLOAD_TOTAL_MB} MB.")
        coletados.append((_sanitize_filename(up.filename or "arquivo"), conteudo))

    ofx_bytes, xmls = _separar_arquivos_fiscal(coletados)

    # F-02: parse_lote_xmls é CPU-bound puro (ET.fromstring em N XMLs).
    # Roda em thread separada para nao bloquear o event loop do FastAPI.
    documentos = await asyncio.to_thread(parse_lote_xmls, xmls)
    log.info("fiscal.processar: cliente=%s xmls=%d docs_validos=%d", cid, len(xmls), len(documentos))

    # Persistência docs
    async with SessionLocal() as db:
        chave_para_id = await salvar_documentos_fiscais(db, cid, documentos)

        # TODO(IC-02 / OrgFiscal): apuração CBS/IBS por documento (Reforma Tributária).
        # Quando o serviço da Calculadora existir, para cada documento persistido:
        #   from api.services.calculadora_cbs_ibs import apurar_documento, ORGFISCAL_DISPONIVEL
        #   from api.services.fiscal_persistence import salvar_apuracao
        #   if ORGFISCAL_DISPONIVEL:
        #       ap = await apurar_documento(documento_id=doc_id, xml_path=<path>)
        #       await salvar_apuracao(db, cid, doc_id, ap)  # idempotente por (documento_id, versao_base)
        # Persistir SEMPRE com versao_base + ambiente (gate IC-02 §4); em PILOTO, propagar a ressalva.

        # Cruzamento (opcional, se OFX fornecido)
        transacoes = []
        cruzamentos = []
        scores_conformidade = []
        if ofx_bytes:
            try:
                # F-02: ler_ofx tambem CPU-bound
                transacoes = await asyncio.to_thread(ler_ofx, ofx_bytes)
            except Exception as exc:
                log.warning("fiscal: falha ao ler OFX: %s", type(exc).__name__)
                raise HTTPException(400, "Falha ao ler OFX")
            # F-02: cruzar() faz O(n*m) e e CPU-bound
            cruzamentos = await asyncio.to_thread(cruzar, documentos, transacoes)
            await salvar_cruzamentos(db, cid, cruzamentos, chave_para_id)

            # Conformidade + risco tributário (Sprint 2) — agregacao em dict, CPU-bound
            scores_conformidade = await asyncio.to_thread(
                calcular_conformidade_fornecedor, documentos, transacoes
            )
            riscos = {r.cnpj_fornecedor: r for r in estimar_risco_tributario_anual(scores_conformidade)}
            for sc in scores_conformidade:
                risco_tributario_anual = riscos.get(sc.cnpj_fornecedor)
                classe = classificar_risco(sc)
                await salvar_conformidade(db, cid, sc.cnpj_fornecedor, {
                    "razao_social": sc.razao_social,
                    "periodo_inicio": sc.periodo_inicio,
                    "periodo_fim": sc.periodo_fim,
                    "volume_pago": sc.volume_pago,
                    "volume_nf": sc.volume_nf,
                    "conformidade_pct": sc.conformidade_pct,
                    "n_pagamentos": sc.n_pagamentos,
                    "n_nfes": sc.n_nfes,
                    "risco_classe": classe,
                    "risco_tributario_anual": risco_tributario_anual.risco_anual if risco_tributario_anual else 0.0,
                    "flags": ",".join(sc.flags) if sc.flags else None,
                })
        await db.commit()

    # Agrega por tipo
    tipos = {"NF-e": 0, "CT-e": 0, "NFS-e": 0}
    for d in documentos:
        tipos[d.tipo] = tipos.get(d.tipo, 0) + 1

    # F-04: audit_event para escrita fiscal
    async with SessionLocal() as db_audit:
        await registrar_audit(
            db_audit,
            action="fiscal.processar",
            resource_type="cliente",
            resource_id=cliente_id,
            payload={
                "documentos_processados": len(documentos),
                "documentos_por_tipo": tipos,
                "ofx_transacoes": len(transacoes),
                "fornecedores_classificados": len(scores_conformidade),
            },
            actor=user,
        )
        await db_audit.commit()

    # Auditoria forense (metodologia OrgAudi): regime/teto + risk score + retenções.
    # Substitui o "risco" simplista do cruzamento. Cadastro vem do cache de CNPJ
    # (inline, sem rede) para ligar pós-baixa/MEI; o enriquecimento pesado
    # (BrasilAPI/RFB) roda em background e popula o cache para a próxima análise.
    auditoria = None
    if transacoes:
        cadastro = construir_cadastro(transacoes)
        auditoria = resumo_para_dict(analisar_auditoria(transacoes, cadastro=cadastro))
        background.add_task(enriquecer_cadastro, transacoes)

    return JSONResponse({
        "cliente_id": cliente_id,
        "documentos_processados": len(documentos),
        "documentos_por_tipo": tipos,
        "ofx_transacoes": len(transacoes),
        "cruzamentos": resumo(cruzamentos) if cruzamentos else None,
        "fornecedores_classificados": len(scores_conformidade),
        "auditoria_forense": auditoria,
    })


@router.post("/apurar")
@limiter.limit("30/minute")
async def apurar_cbs_ibs(
    request: Request,
    operacao: OperacaoFiscalInput,
    user: TokenPayload = Depends(current_user),
):
    """Apura CBS/IBS de uma operação (contrato IC-02 §3.2).

    Orquestra o motor de cálculo (stub PILOTO em dev; Calculadora oficial RTC
    hospedada/offline em prod — o OrgConc não recalcula) e persiste o resultado +
    memória de cálculo.
    Resposta = ApuracaoCBSIBS com gate de proveniência (versao_base/ambiente/
    fundamentacao). Em PILOTO os valores são provisórios (§4.2).
    """
    try:
        apuracao = await calculadora_cbs_ibs.apurar(operacao)
    except NotImplementedError as e:
        raise HTTPException(501, str(e))

    if DB_DISPONIVEL and SessionLocal is not None:
        try:
            async with SessionLocal() as db:
                await salvar_apuracao(db, apuracao)
                await db.commit()
        except Exception:
            log.exception("Falha ao persistir apuração CBS/IBS (segue sem persistir)")

    return JSONResponse(apuracao.model_dump(mode="json"))


def _t_data_str(t) -> str:
    d = getattr(t, "data", "") or ""
    return d if isinstance(d, str) else d.isoformat()


async def _ler_dedup_ofx(arquivos: List[UploadFile], conta: str) -> list:
    """Lê 1+ OFX, deduplica por (conta, fitid) e filtra por conta. Compartilhado
    por POST /fiscal/laudo/resumo (JSON)."""
    if not arquivos:
        raise HTTPException(400, "Envie ao menos 1 arquivo OFX.")

    transacoes = []
    total = 0
    for up in arquivos:
        conteudo = await read_limited(up, MAX_UPLOAD_BYTES)
        total += len(conteudo)
        if total > MAX_UPLOAD_TOTAL_BYTES:
            raise HTTPException(413, f"Total de uploads excede {MAX_UPLOAD_TOTAL_MB} MB.")
        if not (up.filename or "").lower().endswith(".ofx"):
            continue
        try:
            transacoes.extend(await asyncio.to_thread(ler_ofx, conteudo))
        except Exception:
            raise HTTPException(400, f"Falha ao ler OFX: {up.filename}")
    if not transacoes:
        raise HTTPException(400, "Nenhum arquivo OFX válido fornecido.")

    # dedup por (conta, fitid) + filtro de conta
    vistos: set = set()
    dedup = []
    for t in transacoes:
        k = (t.conta, t.fitid) if t.fitid else (t.conta, t.data, round(t.valor, 2), t.memo, t.nome)
        if k in vistos:
            continue
        vistos.add(k)
        dedup.append(t)
    if conta:
        dedup = [t for t in dedup if conta in (t.conta or "")]
    if not dedup:
        raise HTTPException(400, "Nenhuma transação para a conta informada.")
    return dedup


@router.post("/laudo")
@limiter.limit("3/minute")
async def gerar_laudo(
    request: Request,
    empresa_cnpj: str = Form(..., description="CNPJ da entidade auditada (14 dígitos)"),
    conta: str = Form("", description="escopar a uma conta (substring do ID da conta no OFX)"),
    arquivos: List[UploadFile] = File(..., description="1+ extratos OFX + (opcional) XMLs/ZIPs de NF-e/CT-e"),
    formato: str = Query("xlsx", description="xlsx | html | pdf"),
    user: TokenPayload = Depends(current_user),
):
    """Laudo Integrado de Auditoria (núcleo único de api.services.laudo_forense).

    Aceita extratos OFX e, opcionalmente, XMLs/ZIPs de NF-e/CT-e — quando enviados,
    o MESMO documento ganha as abas/seções fiscais (12. Documentos Fiscais e
    13. Conformidade Fiscal). Formatos: xlsx (abas), html, pdf (WeasyPrint).
    Usa o cache de CNPJ existente (sem rede em-request). Núcleo compartilhado
    com o caminho assíncrono: api/services/laudo_async.gerar_laudo_documento.
    """
    empresa_cnpj = _normalizar_empresa_cnpj(empresa_cnpj)
    uploads = await _coletar_uploads_laudo(arquivos)
    try:
        saida, fname, mime = await gerar_laudo_documento(
            uploads, empresa_cnpj=empresa_cnpj, conta=conta, formato=formato)
    except LaudoEntradaInvalida as e:
        raise HTTPException(e.status, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    disposition = "inline" if mime.startswith("text/html") else "attachment"
    return Response(
        content=saida,
        media_type=mime,
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )


async def _coletar_uploads_laudo(arquivos: List[UploadFile]) -> list[tuple[str, bytes]]:
    """Lê os uploads dentro dos limites e devolve [(nome, bytes)]."""
    if not arquivos:
        raise HTTPException(400, "Envie ao menos 1 arquivo OFX.")
    uploads: list[tuple[str, bytes]] = []
    total = 0
    for up in arquivos:
        conteudo = await read_limited(up, MAX_UPLOAD_BYTES)
        total += len(conteudo)
        if total > MAX_UPLOAD_TOTAL_BYTES:
            raise HTTPException(413, f"Total de uploads excede {MAX_UPLOAD_TOTAL_MB} MB.")
        uploads.append((up.filename or "arquivo", conteudo))
    return uploads


@router.post("/laudo/async")
@limiter.limit("3/minute")
async def gerar_laudo_async(
    request: Request,
    empresa_cnpj: str = Form(..., description="CNPJ da entidade auditada (14 dígitos)"),
    conta: str = Form("", description="escopar a uma conta (substring do ID da conta no OFX)"),
    arquivos: List[UploadFile] = File(..., description="1+ extratos OFX + (opcional) XMLs/ZIPs de NF-e/CT-e"),
    formato: str = Query("xlsx", description="xlsx | html | pdf"),
    user: TokenPayload = Depends(current_user),
):
    """Versão assíncrona do laudo (P1 #9): enfileira e devolve job_id.

    O worker (api/services/job_queue) gera o MESMO documento do endpoint
    síncrono. Polling em GET /jobs/{id}; download em GET /jobs/{id}/resultado.
    Requer banco configurado e organização no token (o job pertence à org).
    """
    if not DB_DISPONIVEL or SessionLocal is None:
        raise HTTPException(503, "Fila de jobs requer banco de dados configurado.")
    if not user.org_id:
        raise HTTPException(403, "Job assíncrono requer organização no token.")
    empresa_cnpj = _normalizar_empresa_cnpj(empresa_cnpj)
    formato = (formato or "xlsx").lower()
    if formato not in FORMATOS_LAUDO:
        raise HTTPException(400, f"formato invalido: use {sorted(FORMATOS_LAUDO)}")
    uploads = await _coletar_uploads_laudo(arquivos)
    if not any((n or "").lower().endswith(".ofx") for n, _ in uploads):
        raise HTTPException(400, "Nenhum arquivo OFX válido fornecido.")

    from sqlalchemy import func, select
    from api.db.models import Job
    from api.services.job_queue import (
        STATUS_EXECUTANDO,
        STATUS_PENDENTE,
        TIPO_LAUDO,
        empacotar_uploads,
    )

    org_uuid = uuid.UUID(user.org_id)
    job = Job(
        org_id=org_uuid,
        tipo=TIPO_LAUDO,
        params={"empresa_cnpj": empresa_cnpj, "conta": conta, "formato": formato},
        arquivos=empacotar_uploads(uploads),
    )
    async with SessionLocal() as db:
        # #37: hard-limit de jobs em aberto por org (anti-DoS na fila).
        # RLS (org_isolation) ja escopa a tabela jobs a org do token.
        em_aberto = (await db.execute(
            select(func.count(Job.id)).where(
                Job.status.in_((STATUS_PENDENTE, STATUS_EXECUTANDO))
            )
        )).scalar() or 0
        if em_aberto >= MAX_JOBS_LAUDO_POR_ORG:
            raise HTTPException(
                429,
                f"Limite de {MAX_JOBS_LAUDO_POR_ORG} jobs em aberto por organização "
                "atingido. Aguarde a conclusão dos jobs pendentes.",
            )
        db.add(job)
        await db.commit()
        job_id = str(job.id)
    log.info("laudo async enfileirado: job=%s formato=%s", job_id, formato)
    return JSONResponse(status_code=202, content={
        "job_id": job_id,
        "status": "PENDENTE",
        "polling": f"/v1/jobs/{job_id}",
        "resultado": f"/v1/jobs/{job_id}/resultado",
    })


@router.post("/laudo/resumo")
@limiter.limit("6/minute")
async def laudo_resumo(
    request: Request,
    background: BackgroundTasks,
    empresa_cnpj: str = Form(..., description="CNPJ da entidade auditada (14 dígitos)"),
    conta: str = Form("", description="escopar a uma conta (substring do ID, ex: 158083)"),
    arquivos: List[UploadFile] = File(..., description="1+ extratos OFX"),
    user: TokenPayload = Depends(current_user),
):
    """Resumo forense JSON (regime×teto + heatmap + sinais + top disposições) dos
    MESMOS OFX do laudo. Alimenta a aba 'Auditoria Forense' do frontend; o XLSX
    completo de 11 abas vem de POST /fiscal/laudo.

    Determinístico e sem rede em-request: usa o cache de CNPJ para situação/porte
    (pós-baixa, MEI-teto). CNPJs ainda não cacheados disparam enriquecimento COMPLETO
    em background (enrich_all) — a próxima análise vem com pós-baixa fiel. O campo
    `enriquecimento_pendente` informa quantos faltam para a UI sugerir re-análise.
    """
    empresa_cnpj = _normalizar_empresa_cnpj(empresa_cnpj)
    dedup = await _ler_dedup_ofx(arquivos, conta)

    def _analisar():
        from api.matchers.cnpj_enricher import _carregar_cache
        cache = _carregar_cache()
        cadastro = construir_cadastro(dedup, cache)
        resumo_aud = resumo_para_dict(analisar_auditoria(dedup, cadastro=cadastro))
        empresa = laudo.construir_empresa(empresa_cnpj, cache)
        faltantes = [c for c in cnpjs_das_transacoes(dedup) if c not in cache]
        return resumo_aud, empresa, faltantes

    resumo_aud, empresa, faltantes = await asyncio.to_thread(_analisar)
    # CNPJs não cacheados → enriquece TODOS em background (pós-baixa fiel na próxima).
    if faltantes:
        background.add_task(enriquecer_cadastro, dedup, enrich_all=True)
    datas = sorted(_t_data_str(t)[:10] for t in dedup if _t_data_str(t))
    return JSONResponse({
        "empresa": {
            "cnpj": empresa.get("cnpj", empresa_cnpj),
            "razao_social": empresa.get("razao_social", "—"),
            "porte": empresa.get("porte_declarado", "—"),
            "situacao": empresa.get("situacao", "—"),
            "cnae": empresa.get("cnae_principal", "—"),
        },
        "conta": conta or None,
        "periodo": {
            "inicio": datas[0] if datas else None,
            "fim": datas[-1] if datas else None,
        },
        "enriquecimento_pendente": len(faltantes),
        **resumo_aud,
    })


@router.get("/conformidade/{cliente_id}")
async def conformidade_cliente(
    cliente_id: str,
    classe_minima: Optional[str] = None,
    user: TokenPayload = Depends(current_user),
):
    """Score consolidado de conformidade fiscal por fornecedor.

    Query params:
    - classe_minima: BAIXO|MEDIO|ALTO|CRITICO (filtra >= classe)
    """
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "cliente_id deve ser UUID válido")
    autorizar_cliente(user, cliente_id)
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")

    async with SessionLocal() as db:
        rows = await listar_conformidade(db, cid, classe_minima)

    return JSONResponse({
        "cliente_id": cliente_id,
        "total": len(rows),
        "fornecedores": [
            {
                "cnpj": r.cnpj_fornecedor,
                "razao_social": r.razao_social,
                "volume_pago": float(r.volume_pago or 0),
                "volume_nf": float(r.volume_nf or 0),
                "conformidade_pct": float(r.conformidade_pct or 0),
                "n_pagamentos": r.n_pagamentos,
                "n_nfes": r.n_nfes,
                "risco_classe": r.risco_classe,
                "risco_tributario_anual": float(r.risco_tributario_anual or 0),
                "flags": (r.flags or "").split(",") if r.flags else [],
                "periodo_inicio": r.periodo_inicio.isoformat() if r.periodo_inicio else None,
                "periodo_fim": r.periodo_fim.isoformat() if r.periodo_fim else None,
            } for r in rows
        ],
    })


@router.get("/gap/{cliente_id}")
async def gaps_fiscais(
    cliente_id: str,
    user: TokenPayload = Depends(current_user),
):
    """Lista cruzamentos com status SEM_NF (pagamentos sem documento)."""
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "cliente_id deve ser UUID válido")
    autorizar_cliente(user, cliente_id)
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")

    async with SessionLocal() as db:
        rows = await listar_cruzamentos(db, cid, status="SEM_NF", limit=1000)

    return JSONResponse({
        "cliente_id": cliente_id,
        "total": len(rows),
        "gaps": [
            {
                "id": str(r.id),
                "status": r.status,
                "diferenca_valor": float(r.diferenca_valor or 0),
                "diferenca_dias": r.diferenca_dias,
                "criado_em": r.criado_em.isoformat() if r.criado_em else None,
            } for r in rows
        ],
    })


@router.get("/risco-tributario/{cliente_id}")
async def risco_tributario(
    cliente_id: str,
    user: TokenPayload = Depends(current_user),
):
    """Estimativa de risco tributário consolidado em Lucro Real.

    Combina:
    - Risco por despesa indedutível (RIR/2018 art. 311) por fornecedor
    - Estimativa de retenções não recolhidas (PIS+COFINS+CSLL+IRRF+INSS)
    - Distribuição por classe de risco
    - Top fornecedores por risco
    """
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "cliente_id deve ser UUID válido")
    autorizar_cliente(user, cliente_id)
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")

    async with SessionLocal() as db:
        rows = await listar_conformidade(db, cid)

    by_classe = {"BAIXO": 0.0, "MEDIO": 0.0, "ALTO": 0.0, "CRITICO": 0.0}
    by_count = {"BAIXO": 0, "MEDIO": 0, "ALTO": 0, "CRITICO": 0}
    por_flag: dict[str, float] = {}
    top: list[dict] = []
    volume_pj = 0.0
    for r in rows:
        risco = float(r.risco_tributario_anual or 0)
        by_classe[r.risco_classe] = by_classe.get(r.risco_classe, 0) + risco
        by_count[r.risco_classe] = by_count.get(r.risco_classe, 0) + 1
        flags = (r.flags or "").split(",") if r.flags else []
        for f in flags:
            if f:
                por_flag[f] = por_flag.get(f, 0) + risco
        volume_pj += float(r.volume_pago or 0)
        if risco > 0:
            top.append({
                "cnpj": r.cnpj_fornecedor,
                "razao_social": r.razao_social,
                "risco_anual": risco,
                "classe": r.risco_classe,
                "flags": [f for f in flags if f],
            })
    top.sort(key=lambda x: -x["risco_anual"])

    # Estimativa de retenções (apenas sobre volume PJ; PF não persistido aqui)
    retencoes = estimar_retencoes_nao_recolhidas(
        volume_pago_pj=volume_pj,
        volume_pago_pf=0.0,
        meses_observados=5,
    )

    total_indedutivel = sum(by_classe.values())
    total_geral = round(total_indedutivel + retencoes["total_anual"], 2)

    return JSONResponse({
        "cliente_id": cliente_id,
        "risco_total_anual": total_geral,
        "risco_despesa_indedutivel_anual": round(total_indedutivel, 2),
        "risco_retencoes_anual": retencoes["total_anual"],
        "por_classe_risco": {k: round(v, 2) for k, v in by_classe.items()},
        "por_flag": {k: round(v, 2) for k, v in por_flag.items()},
        "contagem_fornecedores": by_count,
        "total_fornecedores": len(rows),
        "top_10_fornecedores": top[:10],
        "retencoes": retencoes,
        "regime_pressuposto": "LUCRO_REAL",
        "aliquota_aplicada_pct": 34.0,  # IRPJ 25% + CSLL 9%
        "metodologia": "cruzamento_simples_doc_pagamento",
        "aviso": (
            "INDICADOR conservador derivado do cruzamento doc×pagamento — superestima "
            "quando o extrato não traz CNPJ no memo (match baixo em dados reais). "
            "NÃO é conclusão de auditoria. O achado central da auditoria forense é o "
            "múltiplo do teto de regime — ver 'auditoria_forense' em POST /fiscal/processar."
        ),
    })


@router.post("/gerar-carta/{cliente_id}")
@limiter.limit("5/minute")
async def gerar_carta(
    request: Request,
    cliente_id: str,
    user: TokenPayload = Depends(current_user),
):
    """Gera Carta de Constatação auto-renderizada a partir do banco.

    Persiste versão em `carta_versao` e retorna PDF inline (base64).
    """
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "cliente_id deve ser UUID válido")
    autorizar_cliente(user, cliente_id)
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")

    import base64
    import hashlib

    async with SessionLocal() as db:
        # Conta versões anteriores para incremento
        from sqlalchemy import func, select as _select
        from api.db.models import CartaVersao
        n_anteriores = (
            await db.execute(
                _select(func.count(CartaVersao.id)).where(CartaVersao.cliente_id == cid)
            )
        ).scalar() or 0
        versao = f"auto-{n_anteriores + 1}"

        resultado = await gerar_carta_automatica(db, cid, versao=versao)
        md_text = resultado["markdown"]
        payload_hash = hashlib.sha256(md_text.encode("utf-8")).hexdigest()

        nova_versao = CartaVersao(
            cliente_id=cid,
            versao=versao,
            risco_total=resultado["risco_total"],
            total_fornecedores=resultado["total_fornecedores"],
            payload_hash=payload_hash,
            markdown=md_text,
        )
        db.add(nova_versao)
        # F-04: audit trail da geracao
        await registrar_audit(
            db,
            action="fiscal.carta_gerada",
            resource_type="carta_versao",
            resource_id=str(nova_versao.id),
            payload={
                "cliente_id": cliente_id,
                "versao": versao,
                "risco_total": float(resultado["risco_total"] or 0),
                "total_fornecedores": resultado["total_fornecedores"],
                "payload_hash": payload_hash,
            },
            actor=user,
        )
        await db.commit()

    # PDF (best effort)
    pdf_bytes = await renderizar_pdf_async(resultado["html"])
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii") if pdf_bytes else None

    return JSONResponse({
        "cliente_id": cliente_id,
        "cliente_nome": resultado["cliente_nome"],
        "versao": versao,
        "risco_total": resultado["risco_total"],
        "total_fornecedores": resultado["total_fornecedores"],
        "payload_hash": payload_hash,
        "markdown": md_text,
        "pdf_base64": pdf_b64,
    })


@router.get("/cartas/{cliente_id}")
async def listar_cartas(
    cliente_id: str,
    user: TokenPayload = Depends(current_user),
):
    """Lista versões da Carta de Constatação geradas para o cliente."""
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "cliente_id deve ser UUID válido")
    autorizar_cliente(user, cliente_id)
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")

    from sqlalchemy import select as _select
    from api.db.models import CartaVersao
    async with SessionLocal() as db:
        stmt = (
            _select(CartaVersao)
            .where(CartaVersao.cliente_id == cid)
            .order_by(CartaVersao.gerado_em.desc())
        )
        rows = (await db.execute(stmt)).scalars().all()

    return JSONResponse({
        "cliente_id": cliente_id,
        "total": len(rows),
        "cartas": [
            {
                "id": str(r.id),
                "versao": r.versao,
                "risco_total": float(r.risco_total or 0),
                "total_fornecedores": r.total_fornecedores,
                "payload_hash": r.payload_hash,
                "gerado_em": r.gerado_em.isoformat() if r.gerado_em else None,
            } for r in rows
        ],
    })


@router.get("/documentos/{cliente_id}")
async def listar_documentos(
    cliente_id: str,
    limit: int = 100,
    user: TokenPayload = Depends(current_user),
):
    """Lista documentos fiscais persistidos para o cliente."""
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "cliente_id deve ser UUID válido")
    autorizar_cliente(user, cliente_id)
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")

    async with SessionLocal() as db:
        docs = await listar_documentos_por_cliente(db, cid, limit=limit)

    return JSONResponse({
        "cliente_id": cliente_id,
        "total": len(docs),
        "documentos": [
            {
                "id": str(d.id),
                "tipo": d.tipo,
                "modelo": d.modelo,
                "chave": d.chave,
                "numero": d.numero,
                "data_emissao": d.data_emissao.isoformat() if d.data_emissao else None,
                "emit_cnpj": d.emit_cnpj,
                "emit_nome": d.emit_nome,
                "valor_total": float(d.valor_total or 0),
            } for d in docs
        ],
    })
