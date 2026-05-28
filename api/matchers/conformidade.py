"""Score de Conformidade Fiscal por fornecedor.

Sprint 2 do Plano de Integração Fiscal.

Algoritmo:
1. Para cada CNPJ fornecedor (emit_cnpj nos pagamentos OFX), agrega:
   - volume_pago = soma dos valores pagos
   - volume_nf = soma dos valores das NF-es emitidas por esse CNPJ
   - n_pagamentos, n_nfes
2. conformidade_pct = (volume_nf / volume_pago) * 100, cap 100
3. Classifica:
   - >=80%: BAIXO
   - 50-79%: MEDIO
   - 20-49%: ALTO
   - <20%: CRITICO
4. Detecta flags:
   - REDE_FROTA_TYPE: vol >= 100k e NF == 0 (cartão de frota sem NF)
   - MEI_SEM_CTE: fornecedor classificado como MEI sem CT-e
   - PARTE_RELACIONADA: contém "LOCAR" ou nome do sócio no nome
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Optional

from api.matchers.cascata import Transacao
from api.matchers.xml_fiscal import DocumentoFiscalLido

RX_CNPJ = re.compile(r"(\d{2})[.](\d{3})[.](\d{3})[ /](\d{4})[-](\d{2})")
RX_CNPJ_BRUTO = re.compile(r"\b(\d{14})\b")


@dataclass
class ConformidadeScore:
    cnpj_fornecedor: str
    razao_social: str
    periodo_inicio: Optional[date]
    periodo_fim: Optional[date]
    volume_pago: float
    volume_nf: float
    conformidade_pct: float
    n_pagamentos: int
    n_nfes: int
    risco_classe: str
    flags: list[str] = field(default_factory=list)


def _classe(pct: float) -> str:
    if pct >= 80:
        return "BAIXO"
    if pct >= 50:
        return "MEDIO"
    if pct >= 20:
        return "ALTO"
    return "CRITICO"


def _extrair_cnpj(t: Transacao) -> Optional[str]:
    texto = f"{t.nome or ''} {t.memo or ''}"
    m = RX_CNPJ.search(texto)
    if m:
        return "".join(m.groups())
    m2 = RX_CNPJ_BRUTO.search(texto)
    if m2:
        return m2.group(1)
    return None


def _detectar_flags(
    nome: str,
    cnae: str,
    volume_pago: float,
    volume_nf: float,
    is_mei: bool,
    n_ctes: int,
    nomes_socios: Iterable[str] = (),
) -> list[str]:
    flags: list[str] = []
    nome_up = (nome or "").upper()

    # REDE FROTA TYPE: pagamentos relevantes sem NF-e
    if volume_pago >= 100_000 and volume_nf == 0:
        flags.append("REDE_FROTA_TYPE")

    # MEI sem CT-e (Constatação VIII caso 2)
    if is_mei and cnae.startswith("4930") and n_ctes == 0:
        flags.append("MEI_SEM_CTE")

    # Parte relacionada (heurística)
    for socio in nomes_socios:
        if socio and socio.upper() in nome_up:
            flags.append("PARTE_RELACIONADA")
            break
    if "LOCAR" in nome_up and "BOVINOS" not in nome_up:
        if "PARTE_RELACIONADA" not in flags:
            flags.append("PARTE_RELACIONADA")

    return flags


def calcular_conformidade_fornecedor(
    documentos: Iterable[DocumentoFiscalLido],
    transacoes: Iterable[Transacao],
    cnae_por_cnpj: Optional[dict[str, str]] = None,
    nomes_socios: Iterable[str] = (),
    is_mei_por_cnpj: Optional[dict[str, bool]] = None,
) -> list[ConformidadeScore]:
    """Calcula score de conformidade para cada fornecedor identificado.

    Cruza pagamentos OFX (saídas) com NF-es/CT-es por CNPJ do emitente.
    """
    cnae_por_cnpj = cnae_por_cnpj or {}
    is_mei_por_cnpj = is_mei_por_cnpj or {}

    # Agrega pagamentos por CNPJ
    pag_por_cnpj: dict[str, dict] = defaultdict(lambda: {"vol": 0.0, "n": 0, "datas": [], "nome": ""})
    for t in transacoes:
        if t.valor >= 0:
            continue
        cnpj = _extrair_cnpj(t)
        if not cnpj:
            continue
        pag_por_cnpj[cnpj]["vol"] += abs(t.valor)
        pag_por_cnpj[cnpj]["n"] += 1
        pag_por_cnpj[cnpj]["nome"] = pag_por_cnpj[cnpj]["nome"] or (t.nome or "")
        d = t.data
        if isinstance(d, str):
            try:
                from datetime import datetime
                d = datetime.strptime(d[:10], "%Y-%m-%d").date()
            except ValueError:
                d = None
        if isinstance(d, date):
            pag_por_cnpj[cnpj]["datas"].append(d)

    # Agrega NF-es por CNPJ emitente
    nfe_por_cnpj: dict[str, dict] = defaultdict(lambda: {"vol": 0.0, "n": 0, "n_ctes": 0, "nome": ""})
    for d in documentos:
        if not d.emit_cnpj:
            continue
        nfe_por_cnpj[d.emit_cnpj]["vol"] += d.valor_total
        nfe_por_cnpj[d.emit_cnpj]["n"] += 1
        nfe_por_cnpj[d.emit_cnpj]["nome"] = d.emit_nome or nfe_por_cnpj[d.emit_cnpj]["nome"]
        if d.tipo == "CT-e":
            nfe_por_cnpj[d.emit_cnpj]["n_ctes"] += 1

    # Conjuga ambos os universos (paga ou emite)
    cnpjs = set(pag_por_cnpj) | set(nfe_por_cnpj)
    scores: list[ConformidadeScore] = []
    for cnpj in cnpjs:
        p = pag_por_cnpj.get(cnpj, {"vol": 0, "n": 0, "datas": [], "nome": ""})
        d = nfe_por_cnpj.get(cnpj, {"vol": 0, "n": 0, "n_ctes": 0, "nome": ""})
        vol_pago = p["vol"]
        vol_nf = d["vol"]
        if vol_pago > 0:
            pct = min(100.0, (vol_nf / vol_pago) * 100)
        elif vol_nf > 0:
            pct = 100.0  # documento sem pagamento mas existe NF — conformidade técnica plena
        else:
            pct = 0.0
        razao = d["nome"] or p["nome"]
        datas = p["datas"]
        flags = _detectar_flags(
            nome=razao,
            cnae=cnae_por_cnpj.get(cnpj, ""),
            volume_pago=vol_pago,
            volume_nf=vol_nf,
            is_mei=is_mei_por_cnpj.get(cnpj, False),
            n_ctes=d["n_ctes"],
            nomes_socios=nomes_socios,
        )
        scores.append(ConformidadeScore(
            cnpj_fornecedor=cnpj,
            razao_social=razao[:200],
            periodo_inicio=min(datas) if datas else None,
            periodo_fim=max(datas) if datas else None,
            volume_pago=round(vol_pago, 2),
            volume_nf=round(vol_nf, 2),
            conformidade_pct=round(pct, 2),
            n_pagamentos=p["n"],
            n_nfes=d["n"],
            risco_classe=_classe(pct) if vol_pago > 0 else "BAIXO",
            flags=flags,
        ))
    # Ordena por volume pago desc
    scores.sort(key=lambda s: -s.volume_pago)
    return scores


def classificar_risco(score: ConformidadeScore) -> str:
    """Retorna BAIXO/MEDIO/ALTO/CRITICO com base no score e flags."""
    if "REDE_FROTA_TYPE" in score.flags or "MEI_SEM_CTE" in score.flags:
        return "CRITICO"
    return score.risco_classe
