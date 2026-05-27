"""Router /matchers — conciliação automática via cascata de matchers (OrgNeural2)."""
from __future__ import annotations

import io
import logging
import re
import zipfile
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from api.core.config import MAX_UPLOAD_BYTES, MAX_UPLOAD_TOTAL_BYTES, MAX_UPLOAD_TOTAL_MB
from api.core.rate_limit import limiter
from api.matchers.cascata import Disposicao, classificar, ler_ofx
from api.matchers.nfe import resolver as resolver_nfe
from api.services.auth import TokenPayload, current_user
from api.services.storage import read_limited

router = APIRouter(tags=["matchers"], prefix="/matchers")
log = logging.getLogger("orgconc.matchers")

_SAFE_FILENAME_RE = re.compile(r"[^\w.\-]")
_OFX_EXT = (".ofx",)
_XML_EXT = (".xml",)
_ZIP_EXT = (".zip",)


def _sanitize_filename(name: str) -> str:
    return _SAFE_FILENAME_RE.sub("_", name)[:120] or "arquivo"


def _separar_arquivos(arquivos: list[tuple[str, bytes]]) -> tuple[bytes, list[tuple[str, bytes]]]:
    """Separa OFX (1 arquivo) dos XMLs (lista). Expande ZIP em memória."""
    ofx_bytes: Optional[bytes] = None
    xmls: list[tuple[str, bytes]] = []

    for filename, conteudo in arquivos:
        nome_lower = filename.lower()
        if nome_lower.endswith(_OFX_EXT):
            if ofx_bytes is not None:
                raise HTTPException(400, "Envie apenas 1 arquivo OFX por requisição.")
            ofx_bytes = conteudo
        elif nome_lower.endswith(_XML_EXT):
            xmls.append((filename, conteudo))
        elif nome_lower.endswith(_ZIP_EXT):
            try:
                with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
                    for member in zf.namelist():
                        if member.lower().endswith(_XML_EXT):
                            with zf.open(member) as fh:
                                xmls.append((member, fh.read()))
                        elif member.lower().endswith(_OFX_EXT):
                            with zf.open(member) as fh:
                                if ofx_bytes is not None:
                                    raise HTTPException(
                                        400,
                                        "ZIP contém mais de 1 OFX; envie apenas 1.",
                                    )
                                ofx_bytes = fh.read()
            except zipfile.BadZipFile:
                raise HTTPException(400, f"Arquivo {filename} não é um ZIP válido.")
        else:
            log.warning("matchers: ignorando arquivo com extensão não suportada: %s", filename)

    if ofx_bytes is None:
        raise HTTPException(400, "Nenhum arquivo OFX fornecido (nem direto, nem em ZIP).")

    return ofx_bytes, xmls


@router.post("/conciliar")
@limiter.limit("10/minute")
async def conciliar_matchers(
    request: Request,
    cliente_id: str = Form(..., description="UUID do cliente"),
    arquivos: List[UploadFile] = File(..., description="OFX + XMLs de NF-e (ou ZIP)"),
    user: TokenPayload = Depends(current_user),
):
    """Conciliação automática via cascata de matchers.

    Aceita:
    - 1 arquivo OFX (extrato)
    - N arquivos XML de NF-e OU 1 ZIP contendo XMLs (e opcionalmente o OFX)

    Retorna disposições de cada transação (RESOLVIDO_NFE, NF_NAO_ENCONTRADA, etc.).
    """
    if not arquivos:
        raise HTTPException(400, "Envie ao menos 1 arquivo.")

    # Leitura streaming com limites
    coletados: list[tuple[str, bytes]] = []
    total = 0
    for up in arquivos:
        conteudo = await read_limited(up, MAX_UPLOAD_BYTES)
        total += len(conteudo)
        if total > MAX_UPLOAD_TOTAL_BYTES:
            raise HTTPException(
                413,
                f"Total de uploads excede {MAX_UPLOAD_TOTAL_MB} MB.",
            )
        coletados.append((_sanitize_filename(up.filename or "arquivo"), conteudo))

    # Separa OFX vs XMLs (expandindo ZIPs)
    ofx_bytes, xmls = _separar_arquivos(coletados)

    # Pipeline: parser OFX → classificador → matchers
    try:
        transacoes = ler_ofx(ofx_bytes)
    except Exception as exc:  # noqa: BLE001
        log.warning("matchers: falha ao ler OFX: %s", type(exc).__name__)
        raise HTTPException(400, "Falha ao ler OFX — verifique o arquivo.")

    resultados = [classificar(t) for t in transacoes]
    nfe_resolvidas = await resolver_nfe(resultados, xmls)

    # Constrói tabela de disposições (PR 1: apenas estágio 2 = NFe;
    # demais transações ficam pendentes para próximos PRs)
    by_idx: dict[int, Disposicao] = {}
    fitid_to_idx = {r.transacao.fitid: i for i, r in enumerate(resultados)}

    for nr in nfe_resolvidas:
        idx = fitid_to_idx.get(nr.resultado.transacao.fitid, -1)
        if idx < 0:
            continue
        if nr.status == "RESOLVIDO":
            disp = Disposicao(
                transacao=nr.resultado.transacao,
                estagio=2,
                disposicao="RESOLVIDO_NFE",
                contraparte=nr.nota.emit_nome if nr.nota else "",
                origem="nfe",
                flag=nr.flag,
                nfe_chave=nr.nota.chave if nr.nota else "",
            )
        else:
            disp = Disposicao(
                transacao=nr.resultado.transacao,
                estagio=2,
                disposicao="PENDENTE_REVISAO",
                origem="match_nfe",
                flag=nr.flag,
            )
        by_idx[idx] = disp

    # Demais transações: marca conforme estágio classificado (sem matcher ainda em PR1)
    for i, r in enumerate(resultados):
        if i in by_idx:
            continue
        if r.metodo == "transferencia_interna":
            by_idx[i] = Disposicao(
                transacao=r.transacao, estagio=0,
                disposicao="TRANSFERENCIA_INTERNA",
                origem="regra",
                flag="nao e evento economico — excluir da conciliacao",
            )
        elif r.metodo == "tarifa_bancaria":
            by_idx[i] = Disposicao(
                transacao=r.transacao, estagio=3,
                disposicao="TARIFA_BANCARIA", origem="regra",
            )
        else:
            by_idx[i] = Disposicao(
                transacao=r.transacao, estagio=r.estagio,
                disposicao="PENDENTE_MATCHER",
                origem=r.metodo,
                flag="matcher do estagio ainda nao implementado (PR1 cobre apenas NFe)",
            )

    disposicoes = [by_idx[i] for i in range(len(resultados))]

    # Serializa resposta
    def _serial(d: Disposicao) -> dict:
        return {
            "data": d.transacao.data,
            "tipo": d.transacao.tipo,
            "valor": d.transacao.valor,
            "fitid": d.transacao.fitid,
            "memo": d.transacao.memo,
            "nome": d.transacao.nome,
            "estagio": d.estagio,
            "disposicao": d.disposicao,
            "contraparte": d.contraparte,
            "conta_contabil": d.conta_contabil,
            "origem": d.origem,
            "flag": d.flag,
            "nfe_chave": d.nfe_chave,
        }

    automatizadas = sum(
        1 for d in disposicoes
        if d.disposicao.startswith("RESOLVIDO_")
        or d.disposicao in ("TRANSFERENCIA_INTERNA", "TARIFA_BANCARIA")
    )
    return JSONResponse({
        "cliente_id": cliente_id,
        "total_transacoes": len(disposicoes),
        "automatizadas": automatizadas,
        "taxa_automatizacao_pct": round(100 * automatizadas / len(disposicoes), 1) if disposicoes else 0.0,
        "disposicoes": [_serial(d) for d in disposicoes],
        "xmls_indexados": len(xmls),
    })
