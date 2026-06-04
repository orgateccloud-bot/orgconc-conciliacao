"""Cruzamento entre documentos fiscais (NF-e/CT-e/NFS-e) e transações bancárias (OFX).

Sprint 1 do Plano de Integração Fiscal: este módulo recebe a lista de
DocumentoFiscalLido + transações OFX e produz registros de cruzamento.

Algoritmo:
1. Indexa documentos por (CNPJ emitente, valor arredondado, mês).
2. Para cada transação OFX (saída/pagamento), procura matches.
3. Para cada documento sem pagamento correspondente, registra SEM_PAGAMENTO.
4. Para cada transação sem documento, registra SEM_NF (gap fiscal).

Matching N:M:
- 1:1 exato (valor dentro da tolerância, na janela temporal)
- 1:N: um pagamento quita a soma de vários documentos (pagamento agregado)
- N:1: vários pagamentos quitam um documento (parcelamento)

Tolerâncias:
- Valor: max(R$ 0,01, 2% do valor) — o percentual absorve juros/multa
- Janela temporal: 30 dias entre emissão e pagamento
Documentos CANCELADA/DENEGADA são ignorados (sem validade fiscal).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional

from api.matchers.cascata import Transacao
from api.matchers.xml_fiscal import DocumentoFiscalLido

RX_CNPJ = re.compile(r"(\d{2})[.](\d{3})[.](\d{3})[ /](\d{4})[-](\d{2})")
RX_CNPJ_BRUTO = re.compile(r"\b(\d{14})\b")

TOLERANCIA_VALOR = 0.01
TOLERANCIA_PCT = 0.02   # 2% para absorver juros/multa em parcelamentos
JANELA_DIAS = 30


def _dentro_tol(a: float, b: float) -> bool:
    """True se a ≈ b dentro de max(R$0,01, 2% de b)."""
    return abs(a - b) <= max(TOLERANCIA_VALOR, abs(b) * TOLERANCIA_PCT)


def _na_janela(d1: Optional[date], d2: Optional[date]) -> bool:
    """True se as datas estão dentro da janela (ou se alguma é desconhecida)."""
    if d1 is None or d2 is None:
        return True
    return abs((d1 - d2).days) <= JANELA_DIAS


@dataclass
class CruzamentoResult:
    status: str  # CASADO | VALOR_DIVERGENTE | SEM_PAGAMENTO | SEM_NF
    documento: Optional[DocumentoFiscalLido] = None
    transacao: Optional[Transacao] = None
    diferenca_valor: Optional[float] = None
    diferenca_dias: Optional[int] = None


def _extrair_cnpj_da_transacao(t: Transacao) -> Optional[str]:
    texto = f"{t.nome or ''} {t.memo or ''}"
    m = RX_CNPJ.search(texto)
    if m:
        return "".join(m.groups())
    m2 = RX_CNPJ_BRUTO.search(texto)
    if m2:
        return m2.group(1)
    return None


def _parse_data(s: str) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _data_transacao(t: Transacao) -> Optional[date]:
    if isinstance(t.data, date):
        return t.data
    if isinstance(t.data, str):
        try:
            return datetime.strptime(t.data[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def cruzar(
    documentos: Iterable[DocumentoFiscalLido],
    transacoes: Iterable[Transacao],
) -> list[CruzamentoResult]:
    """Cruza documentos fiscais com transações OFX.

    Retorna lista de cruzamentos. Cada documento gera no mínimo um registro
    (CASADO ou SEM_PAGAMENTO). Transações sem documento geram SEM_NF.
    """
    # Ignora documentos sem validade fiscal (não contam como cobertura).
    docs = [d for d in documentos
            if getattr(d, "situacao", "AUTORIZADA") not in ("CANCELADA", "DENEGADA")]
    txs_saida = [t for t in transacoes if t.valor < 0]

    # Índices por CNPJ
    docs_por_cnpj: dict[str, list[DocumentoFiscalLido]] = defaultdict(list)
    for d in docs:
        if d.emit_cnpj:
            docs_por_cnpj[d.emit_cnpj].append(d)
    pagtos_por_cnpj: dict[str, list[Transacao]] = defaultdict(list)
    for t in txs_saida:
        cnpj = _extrair_cnpj_da_transacao(t)
        if cnpj:
            pagtos_por_cnpj[cnpj].append(t)

    docs_usados: set[int] = set()
    txs_usadas: set[int] = set()
    resultados: list[CruzamentoResult] = []

    # Por CNPJ: 1:1 exato → 1:N (pagamento agregado) → N:1 (parcelamento)
    for cnpj in set(docs_por_cnpj) | set(pagtos_por_cnpj):
        ds = sorted(docs_por_cnpj.get(cnpj, []),
                    key=lambda d: _parse_data(d.data_emissao) or date.min)
        ps = sorted(pagtos_por_cnpj.get(cnpj, []),
                    key=lambda t: _data_transacao(t) or date.min)

        # 1:1 — um pagamento casa um documento
        for t in ps:
            if id(t) in txs_usadas:
                continue
            vt, dt = abs(t.valor), _data_transacao(t)
            for d in ds:
                if id(d) in docs_usados or not _dentro_tol(d.valor_total, vt):
                    continue
                dd = _parse_data(d.data_emissao)
                if not _na_janela(dt, dd):
                    continue
                dif_dias = abs((dt - dd).days) if dt and dd else None
                resultados.append(CruzamentoResult("CASADO", d, t, round(abs(d.valor_total - vt), 2), dif_dias))
                docs_usados.add(id(d)); txs_usadas.add(id(t))
                break

        # 1:N — um pagamento quita a soma de vários documentos
        for t in ps:
            if id(t) in txs_usadas:
                continue
            vt, dt = abs(t.valor), _data_transacao(t)
            grupo, soma = [], 0.0
            for d in ds:
                if id(d) in docs_usados or not _na_janela(dt, _parse_data(d.data_emissao)):
                    continue
                grupo.append(d); soma += d.valor_total
                if _dentro_tol(soma, vt):
                    break
            if len(grupo) >= 2 and _dentro_tol(soma, vt):
                for d in grupo:
                    resultados.append(CruzamentoResult("CASADO", d, t, round(soma - vt, 2), None))
                    docs_usados.add(id(d))
                txs_usadas.add(id(t))

        # N:1 — vários pagamentos quitam um documento (parcelamento)
        for d in ds:
            if id(d) in docs_usados:
                continue
            dd = _parse_data(d.data_emissao)
            grupo, soma = [], 0.0
            for t in ps:
                if id(t) in txs_usadas or not _na_janela(_data_transacao(t), dd):
                    continue
                grupo.append(t); soma += abs(t.valor)
                if _dentro_tol(soma, d.valor_total):
                    break
            if len(grupo) >= 2 and _dentro_tol(soma, d.valor_total):
                resultados.append(CruzamentoResult("CASADO", d, grupo[0], round(soma - d.valor_total, 2), None))
                docs_usados.add(id(d))
                for t in grupo:
                    txs_usadas.add(id(t))

    # VALOR_DIVERGENTE: pagamento com documento do mesmo CNPJ na janela, sem casar valor
    for t in txs_saida:
        if id(t) in txs_usadas:
            continue
        cnpj = _extrair_cnpj_da_transacao(t)
        if not cnpj or cnpj not in docs_por_cnpj:
            continue
        dt = _data_transacao(t)
        for d in docs_por_cnpj[cnpj]:
            if id(d) in docs_usados or not _na_janela(dt, _parse_data(d.data_emissao)):
                continue
            dd = _parse_data(d.data_emissao)
            dif_dias = abs((dt - dd).days) if dt and dd else None
            resultados.append(CruzamentoResult("VALOR_DIVERGENTE", d, t, round(abs(d.valor_total - abs(t.valor)), 2), dif_dias))
            docs_usados.add(id(d)); txs_usadas.add(id(t))
            break

    # SEM_PAGAMENTO: documentos não utilizados
    for d in docs:
        if id(d) not in docs_usados:
            resultados.append(CruzamentoResult("SEM_PAGAMENTO", documento=d))

    # SEM_NF: pagamentos de saída sem documento
    for t in txs_saida:
        if id(t) not in txs_usadas:
            resultados.append(CruzamentoResult("SEM_NF", transacao=t))

    return resultados


def resumo(resultados: list[CruzamentoResult]) -> dict:
    """Resumo agregado do cruzamento."""
    by_status: dict[str, int] = defaultdict(int)
    vol_por_status: dict[str, float] = defaultdict(float)
    for r in resultados:
        by_status[r.status] += 1
        if r.status == "SEM_NF" and r.transacao is not None:
            vol_por_status["SEM_NF"] += abs(r.transacao.valor)
        elif r.status == "SEM_PAGAMENTO" and r.documento is not None:
            vol_por_status["SEM_PAGAMENTO"] += r.documento.valor_total
        elif r.documento is not None:
            vol_por_status[r.status] += r.documento.valor_total
    return {
        "total": len(resultados),
        "por_status": dict(by_status),
        "volume_por_status": {k: round(v, 2) for k, v in vol_por_status.items()},
    }
