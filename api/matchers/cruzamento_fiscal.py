"""Cruzamento entre documentos fiscais (NF-e/CT-e/NFS-e) e transações bancárias (OFX).

Sprint 1 do Plano de Integração Fiscal: este módulo recebe a lista de
DocumentoFiscalLido + transações OFX e produz registros de cruzamento.

Algoritmo:
1. Indexa documentos por (CNPJ emitente, valor arredondado, mês).
2. Para cada transação OFX (saída/pagamento), procura matches.
3. Para cada documento sem pagamento correspondente, registra SEM_PAGAMENTO.
4. Para cada transação sem documento, registra SEM_NF (gap fiscal).

Tolerâncias:
- Valor: R$ 0,01 (match exato)
- Janela temporal: 30 dias entre emissão e pagamento
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from api.matchers.cascata import Transacao
from api.matchers.xml_fiscal import DocumentoFiscalLido

RX_CNPJ = re.compile(r"(\d{2})[.](\d{3})[.](\d{3})[ /](\d{4})[-](\d{2})")
RX_CNPJ_BRUTO = re.compile(r"\b(\d{14})\b")

TOLERANCIA_VALOR = 0.01
JANELA_DIAS = 30


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
    docs = list(documentos)
    txs = list(transacoes)

    # Indexa documentos por CNPJ do emitente
    docs_por_cnpj: dict[str, list[DocumentoFiscalLido]] = defaultdict(list)
    for d in docs:
        if d.emit_cnpj:
            docs_por_cnpj[d.emit_cnpj].append(d)

    # Marcações de uso
    docs_usados: set[int] = set()
    txs_usadas: set[int] = set()
    resultados: list[CruzamentoResult] = []

    # Etapa 1: Para cada transação de SAÍDA, procura documento correspondente
    for tx_idx, t in enumerate(txs):
        if t.valor >= 0:  # pular entradas
            continue
        valor_tx = abs(t.valor)
        data_tx = _data_transacao(t)
        cnpj_tx = _extrair_cnpj_da_transacao(t)

        candidatos: list[DocumentoFiscalLido] = []
        if cnpj_tx and cnpj_tx in docs_por_cnpj:
            candidatos = docs_por_cnpj[cnpj_tx]

        match_encontrado = False
        for d in candidatos:
            d_idx = id(d)
            if d_idx in docs_usados:
                continue
            # Match por valor
            dif_valor = abs(d.valor_total - valor_tx)
            if dif_valor > TOLERANCIA_VALOR:
                continue
            # Match por janela temporal
            d_data = _parse_data(d.data_emissao)
            dif_dias = None
            if data_tx and d_data:
                dif_dias = abs((data_tx - d_data).days)
                if dif_dias > JANELA_DIAS:
                    continue
            # Match!
            resultados.append(CruzamentoResult(
                status="CASADO",
                documento=d,
                transacao=t,
                diferenca_valor=dif_valor,
                diferenca_dias=dif_dias,
            ))
            docs_usados.add(d_idx)
            txs_usadas.add(tx_idx)
            match_encontrado = True
            break

        # Se não encontrou match por valor, tenta match parcial (mesmo CNPJ e janela, mas valor diferente)
        if not match_encontrado and cnpj_tx and cnpj_tx in docs_por_cnpj:
            for d in candidatos:
                d_idx = id(d)
                if d_idx in docs_usados:
                    continue
                d_data = _parse_data(d.data_emissao)
                if data_tx and d_data:
                    dif_dias = abs((data_tx - d_data).days)
                    if dif_dias > JANELA_DIAS:
                        continue
                # Encontrado documento na janela mas valor diverge
                resultados.append(CruzamentoResult(
                    status="VALOR_DIVERGENTE",
                    documento=d,
                    transacao=t,
                    diferenca_valor=abs(d.valor_total - valor_tx),
                    diferenca_dias=dif_dias if data_tx and d_data else None,
                ))
                docs_usados.add(d_idx)
                txs_usadas.add(tx_idx)
                break

    # Etapa 2: Documentos sem pagamento correspondente
    for d in docs:
        if id(d) not in docs_usados:
            resultados.append(CruzamentoResult(status="SEM_PAGAMENTO", documento=d))

    # Etapa 3: Transações de saída sem documento (gap fiscal)
    for tx_idx, t in enumerate(txs):
        if t.valor >= 0:
            continue
        if tx_idx not in txs_usadas:
            resultados.append(CruzamentoResult(status="SEM_NF", transacao=t))

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
