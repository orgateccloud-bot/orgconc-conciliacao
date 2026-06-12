"""Geração do Laudo Integrado a partir de uploads brutos — núcleo compartilhado.

Extraído de POST /fiscal/laudo para ser reusado pelo caminho assíncrono
(fila de jobs, P1 #9): o endpoint síncrono e o worker chamam a MESMA função,
`gerar_laudo_documento`, garantindo laudo idêntico nos dois fluxos.

Erros de entrada viram `LaudoEntradaInvalida` (o router mapeia p/ HTTPException;
o worker grava como erro do job). Sem dependência de FastAPI aqui.
"""
from __future__ import annotations

import asyncio
import re

from api.services import laudo_forense as laudo

FORMATOS_LAUDO = {"xlsx", "html", "pdf"}

MIMES_LAUDO = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "html": "text/html; charset=utf-8",
    "pdf": "application/pdf",
}

_SAFE_FILENAME_RE = re.compile(r"[^\w.\-]")


def sanitize_filename(name: str) -> str:
    return _SAFE_FILENAME_RE.sub("_", name)[:120] or "arquivo"


class LaudoEntradaInvalida(ValueError):
    """Entrada inválida para a geração do laudo (uploads/formato/conta)."""

    def __init__(self, mensagem: str, status: int = 400):
        super().__init__(mensagem)
        self.status = status


async def gerar_laudo_documento(
    uploads: list[tuple[str, bytes]],
    empresa_cnpj: str,
    conta: str,
    formato: str,
) -> tuple[bytes, str, str]:
    """Gera o Laudo Integrado e devolve (conteúdo, filename, mime).

    `uploads` são pares (nome, bytes) já lidos e dentro dos limites de upload
    (validados pelo chamador). OFX alimenta as transações; XML/ZIP alimentam as
    abas/seções fiscais. A empresa do laudo vive em contextvar isolado por
    thread (laudo_forense.set_empresa) — sem global, sem lock: requests
    síncronos e o worker de jobs podem gerar em paralelo sem race.
    """
    formato = (formato or "xlsx").lower()
    if formato not in FORMATOS_LAUDO:
        raise LaudoEntradaInvalida(f"formato invalido: use {sorted(FORMATOS_LAUDO)}")
    if not uploads:
        raise LaudoEntradaInvalida("Envie ao menos 1 arquivo OFX.")

    transacoes = []
    fiscais: list[tuple[str, bytes]] = []
    for nome_orig, conteudo in uploads:
        nome = (nome_orig or "").lower()
        if nome.endswith(".ofx"):
            try:
                transacoes.extend(await asyncio.to_thread(laudo.ler_ofx, conteudo))
            except Exception:
                raise LaudoEntradaInvalida(f"Falha ao ler OFX: {nome_orig}")
        elif nome.endswith(".xml") or nome.endswith(".zip"):
            fiscais.append((sanitize_filename(nome_orig or "doc"), conteudo))
    if not transacoes:
        raise LaudoEntradaInvalida("Nenhum arquivo OFX válido fornecido.")

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
        raise LaudoEntradaInvalida("Nenhuma transação para a conta informada.")

    def _build():
        from io import BytesIO

        from api.matchers.cnpj_enricher import _carregar_cache
        cache = _carregar_cache()
        # NF-e/CT-e pela própria engine (alimenta as abas/seções fiscais).
        nfes, ctes, _n = laudo.carregar_docs_xmls(fiscais) if fiscais else ([], [], 0)
        todos, saldos = laudo.montar_dados(dedup)
        # _build roda em asyncio.to_thread → cada chamada tem contexto próprio
        empresa = laudo.set_empresa(laudo.construir_empresa(empresa_cnpj, cache))
        razao = empresa.get("razao_social", "laudo")
        wb, stats = laudo.gerar_laudo_workbook(todos, saldos, cache, nfes, ctes)
        if formato == "xlsx":
            buf = BytesIO()
            wb.save(buf)
            return buf.getvalue(), razao
        # html / pdf usam o mesmo stats -> gerar_md -> gerar_html
        md, _totais = laudo.gerar_md(stats)
        html = laudo.gerar_html(md, stats.get("periodo_str", ""))
        return html, razao

    saida, razao = await asyncio.to_thread(_build)
    fname = re.sub(r"[^\w]+", "_", razao).strip("_")[:40] or "laudo"

    if formato == "pdf":
        blob = await laudo.html_para_pdf_bytes(saida, landscape=True)
        if not blob:
            raise RuntimeError("Falha ao gerar PDF.")
        return blob, f"laudo_{fname}.pdf", MIMES_LAUDO["pdf"]
    if formato == "html":
        return saida.encode("utf-8"), f"laudo_{fname}.html", MIMES_LAUDO["html"]
    return saida, f"laudo_{fname}.xlsx", MIMES_LAUDO["xlsx"]
