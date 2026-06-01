"""Heuristicas de auditoria forense para enriquecer a aba Disposicoes.

Implementa os 5 eixos propostos:
  A) Compliance da contraparte (vem do cache CNPJ)
  B) Identificacao unica (FITID, CHECKNUM, Meio)
  C) Detecao de padroes (valor redondo, smurfing, carrossel, acumulado, 1a vez)
  D) Risk Score consolidado (0-100) + classe
  E) Rastreabilidade (periodo fiscal, hash linha, status revisao)
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from api.parsers.constants import GUIA_TRIBUTO_TIPOS


# ────────────────────────────────────────────────────────────────────────
# B) Identificacao - meio de pagamento
# ────────────────────────────────────────────────────────────────────────


_MEIO_PATTERNS = [
    (re.compile(r"\bPIX\b", re.I), "PIX"),
    (re.compile(r"COMPRA\s+(VISA|MASTERCARD|MAESTRO|ELO|HIPER|AMEX)", re.I), "CARTAO"),
    (re.compile(r"\bTED\b", re.I), "TED"),
    (re.compile(r"\bDOC\b", re.I), "DOC"),
    (re.compile(r"\bCHEQUE\b|COMPE", re.I), "CHEQUE/COMPE"),
    (re.compile(r"TARIFA|TAR\.|IOF|JUROS|CSL\b", re.I), "TARIFA"),
    (re.compile(r"\bDARF\b|\bDAS\b|\bGPS\b|\bGNRE\b|\bDAE\b", re.I), "TRIBUTO"),
    (re.compile(r"TRANSF|TRANSFER", re.I), "TRANSF"),
    (re.compile(r"BOLETO|TIT\.COMPE|TIT\.PROP", re.I), "BOLETO"),
]


def detectar_meio(memo: str, nome: str) -> str:
    """Identifica o meio de pagamento via heuristica no memo+nome."""
    texto = (memo or "") + " " + (nome or "")
    for rx, label in _MEIO_PATTERNS:
        if rx.search(texto):
            return label
    return "OUTRO"


# ────────────────────────────────────────────────────────────────────────
# C) Padroes - valor redondo
# ────────────────────────────────────────────────────────────────────────


def detectar_valor_redondo(valor: float) -> str:
    """Retorna o "nivel" de arredondamento do valor.

    Multiplo de 1000 e mais suspeito que multiplo de 100.
    """
    v = abs(valor)
    if v == 0 or v < 50:
        return ""
    if v == int(v):
        if int(v) % 10_000 == 0:
            return "REDONDO_10K"
        if int(v) % 5_000 == 0:
            return "REDONDO_5K"
        if int(v) % 1_000 == 0:
            return "REDONDO_1K"
        if int(v) % 500 == 0:
            return "REDONDO_500"
        if int(v) % 100 == 0:
            return "REDONDO_100"
    return ""


# ────────────────────────────────────────────────────────────────────────
# C) Padroes - agregados por contraparte (acumulado mes, 1a vez, smurfing, carrossel)
# ────────────────────────────────────────────────────────────────────────


@dataclass
class AgregadosContraparte:
    """Agregados pre-calculados por (cnpj, mes) e por cnpj."""
    # por (cnpj, AAAA-MM)
    acumulado_mes: dict[tuple[str, str], float] = field(default_factory=dict)
    # cnpj -> primeira data em que apareceu
    primeira_data: dict[str, str] = field(default_factory=dict)
    # cnpj -> tem credito? tem debito?
    teve_credito: dict[str, bool] = field(default_factory=dict)
    teve_debito: dict[str, bool] = field(default_factory=dict)
    # (cnpj, data_dia) -> lista de valores absolutos (para deteccao de smurfing)
    valores_dia: dict[tuple[str, str], list[float]] = field(default_factory=dict)
    # limite porte/MEI: pagamentos >R$6.750/mes a um MEI sao red flag
    LIMITE_MEI_MES: float = 6_750.0     # R$ 81.000/12
    LIMITE_SMURFING: float = 10_000.0   # teto Bacen de declaracao


def calcular_agregados(disposicoes) -> AgregadosContraparte:
    """Pre-calcula agregados por contraparte para enriquecimento eficiente."""
    agg = AgregadosContraparte()
    for d in sorted(disposicoes, key=lambda x: x.transacao.data):
        cnpj = _extrair_cnpj_str(d.transacao)
        if not cnpj:
            continue
        t = d.transacao
        # acumulado mes
        mes = t.data[:7]  # AAAA-MM
        agg.acumulado_mes[(cnpj, mes)] = (
            agg.acumulado_mes.get((cnpj, mes), 0.0) + abs(t.valor)
        )
        # 1a vez
        if cnpj not in agg.primeira_data:
            agg.primeira_data[cnpj] = t.data
        # carrossel
        if t.valor > 0:
            agg.teve_credito[cnpj] = True
        else:
            agg.teve_debito[cnpj] = True
        # smurfing
        agg.valores_dia.setdefault((cnpj, t.data), []).append(abs(t.valor))
    return agg


def detectar_smurfing(cnpj: str, data_str: str, agg: AgregadosContraparte) -> str:
    """Detecta smurfing: 3+ pagamentos no mesmo dia para mesma contraparte abaixo de R$10k."""
    if not cnpj:
        return ""
    valores = agg.valores_dia.get((cnpj, data_str), [])
    if len(valores) >= 3 and all(v < agg.LIMITE_SMURFING for v in valores):
        total = sum(valores)
        if total > agg.LIMITE_SMURFING:
            return f"SMURFING ({len(valores)}x R$ {total:,.0f})"
    return ""


def detectar_carrossel(cnpj: str, agg: AgregadosContraparte) -> str:
    """Detecta carrossel: contraparte com credito E debito no mesmo periodo."""
    if not cnpj:
        return ""
    if agg.teve_credito.get(cnpj) and agg.teve_debito.get(cnpj):
        return "CARROSSEL"
    return ""


def detectar_primeira_vez(cnpj: str, data_str: str, agg: AgregadosContraparte) -> str:
    return "1A_VEZ" if cnpj and agg.primeira_data.get(cnpj) == data_str else ""


# ────────────────────────────────────────────────────────────────────────
# D) Risk Score
# ────────────────────────────────────────────────────────────────────────


def calcular_risk_score(
    valor: float,
    disposicao: str,
    situacao: str,
    porte: str,
    meio: str,
    valor_redondo: str,
    smurfing: str,
    carrossel: str,
    primeira_vez: str,
    acumulado_mes: float,
) -> tuple[int, str]:
    """Retorna (score 0-100, classificacao)."""
    score = 0

    # Situacao cadastral (peso 30)
    if "BAIXADA" in situacao or "INAPTA" in situacao:
        score += 30
    elif "SUSPENSA" in situacao:
        score += 15

    # Disposicao critica (peso 40)
    if disposicao == "ALERTA_POS_BAIXA":
        score += 40

    # MEI estourando teto mensal (peso 25)
    if porte == "MICRO EMPRESA" and acumulado_mes > 6_750:
        score += 25
    elif porte == "MICRO EMPRESA" and acumulado_mes > 3_000:
        score += 10

    # Smurfing (peso 25)
    if smurfing:
        score += 25

    # Carrossel (peso 20)
    if carrossel:
        score += 20

    # Valor redondo alto (peso 5-15)
    if valor_redondo in ("REDONDO_10K", "REDONDO_5K") and abs(valor) >= 5_000:
        score += 15
    elif valor_redondo == "REDONDO_1K" and abs(valor) >= 1_000:
        score += 5

    # 1a vez com valor alto (peso 10)
    if primeira_vez == "1A_VEZ" and abs(valor) >= 10_000:
        score += 10

    # Cartao com valor alto (peso 5) - cartao deveria ser despesa pequena
    if meio == "CARTAO" and abs(valor) >= 5_000:
        score += 5

    score = min(score, 100)
    if score >= 70:
        classe = "CRITICO"
    elif score >= 50:
        classe = "ALTO"
    elif score >= 25:
        classe = "MEDIO"
    else:
        classe = "BAIXO"
    return score, classe


# ────────────────────────────────────────────────────────────────────────
# E) Rastreabilidade
# ────────────────────────────────────────────────────────────────────────


def hash_linha(data: str, valor: float, memo: str, fitid: str) -> str:
    """SHA-256 truncado em 16 chars para identificacao unica da linha."""
    base = f"{data}|{valor:.2f}|{memo}|{fitid}".encode("utf-8")
    return hashlib.sha256(base).hexdigest()[:16]


def periodo_fiscal(data: str) -> str:
    """AAAA-MM da data."""
    return data[:7] if data and len(data) >= 7 else ""


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────


_RX_CNPJ_BANK = re.compile(r"(\d{2})[.](\d{3})[.](\d{3})[ /](\d{4})[-](\d{2})")


def _extrair_cnpj_str(t) -> str:
    """Extrai CNPJ do nome/memo da transacao."""
    for fonte in (t.nome or "", t.memo or ""):
        m = _RX_CNPJ_BANK.search(fonte)
        if m:
            return "".join(m.groups())
    return ""


# ────────────────────────────────────────────────────────────────────────
# Classificador Tributario (para aba "Status Tributario")
# ────────────────────────────────────────────────────────────────────────


_RX_IOF = re.compile(r"\bIOF\b|D[ÉE]B\.IOF", re.I)
_RX_TARIFA = re.compile(r"TARIFA|TAR\.", re.I)
_RX_JUROS = re.compile(r"JUROS\s+CONTRATUAIS|JUROS\b", re.I)
_RX_EMPRESTIMO = re.compile(r"EMPR[ÉE]STIMO|D[ÉE]B\.EMPR|LIBERA[ÇC][ÃA]O\s+TD", re.I)
_RX_PIX = re.compile(r"\bPIX\b", re.I)
_RX_TED = re.compile(r"\bTED\b", re.I)
# Derivado da fonte unica (api/parsers/constants.GUIA_TRIBUTO_TIPOS).
_RX_TRIBUTO = re.compile(r"\b(" + "|".join(GUIA_TRIBUTO_TIPOS) + r")\b", re.I)
_RX_CARTAO = re.compile(r"COMPRA\s+(VISA|MASTERCARD|MAESTRO|ELO|HIPER)", re.I)
_RX_MESMA_TIT = re.compile(r"MESMA\s+TIT|TRANSF\.MESMA", re.I)
_RX_BOLETO = re.compile(r"TIT\.COMPE|BOLETO|TIT\.PROP", re.I)
_RX_CPF_MASK = re.compile(r"\*{3}\.\d{3}\.\d{3}-\*{2}")


def classificar_tributario(memo: str, nome: str, valor: float, cnpj: str = "", porte: str = "") -> dict:
    """Classifica a transacao por incidencia tributaria provavel.

    Retorna dict com:
        - categoria: NAO_TRIBUTAVEL, IOF, TARIFA, JUROS, RETENCAO_PJ, RETENCAO_PF,
                     OPERACAO_CREDITO, PIX_RECEBIDO, PAGAMENTO_TRIBUTO, OUTRO
        - tributo: lista de tributos provaveis
        - aliquota_sugerida: % aproximado de retencao
        - valor_retencao: estimativa de retencao na fonte
        - obs: nota textual
    """
    texto = (memo or "") + " " + (nome or "")
    valor_abs = abs(valor)

    # IOF
    if _RX_IOF.search(texto):
        return {
            "categoria": "IOF",
            "tributo": "IOF",
            "aliquota_sugerida": "0.0082%/dia ou 0.38% emissao",
            "valor_retencao": 0.0,  # já é o próprio IOF
            "obs": "Imposto sobre Operacoes Financeiras (auto-cobrado)",
        }

    # Tarifa bancaria
    if _RX_TARIFA.search(texto):
        return {
            "categoria": "TARIFA",
            "tributo": "PIS/COFINS sobre tarifa (responsabilidade do banco)",
            "aliquota_sugerida": "—",
            "valor_retencao": 0.0,
            "obs": "Tarifa bancaria - despesa dedutivel",
        }

    # Juros contratuais / empréstimo
    if _RX_JUROS.search(texto):
        return {
            "categoria": "JUROS",
            "tributo": "IRPJ/CSLL (despesa financeira dedutivel) + IOF de credito",
            "aliquota_sugerida": "dedutivel no lucro",
            "valor_retencao": 0.0,
            "obs": "Juros pagos sao despesa financeira dedutivel",
        }
    if _RX_EMPRESTIMO.search(texto):
        return {
            "categoria": "OPERACAO_CREDITO",
            "tributo": "IOF crédito",
            "aliquota_sugerida": "0.0082%/dia + 0.38% adicional PJ",
            "valor_retencao": round(valor_abs * 0.0038, 2),
            "obs": "Operacao de credito - sujeita a IOF",
        }

    # Pagamento de tributo
    if _RX_TRIBUTO.search(texto):
        m = _RX_TRIBUTO.search(texto)
        return {
            "categoria": "PAGAMENTO_TRIBUTO",
            "tributo": m.group(0).upper(),
            "aliquota_sugerida": "—",
            "valor_retencao": 0.0,
            "obs": f"Pagamento de {m.group(0).upper()} - quitacao tributaria",
        }

    # Transferência mesma titularidade
    if _RX_MESMA_TIT.search(texto):
        return {
            "categoria": "NAO_TRIBUTAVEL",
            "tributo": "Nenhum (transferencia entre contas proprias)",
            "aliquota_sugerida": "—",
            "valor_retencao": 0.0,
            "obs": "Transferencia mesma titularidade - sem fato gerador",
        }

    # PIX recebido
    if _RX_PIX.search(texto) and valor > 0:
        return {
            "categoria": "PIX_RECEBIDO",
            "tributo": "PIS/COFINS (regime de competencia)",
            "aliquota_sugerida": "3.65% (cumul.) ou 9.25% (n-cum.)",
            "valor_retencao": 0.0,
            "obs": "Receita potencial - verificar lastro (NF-e)",
        }

    # PIX emitido para PJ (CNPJ identificado)
    if _RX_PIX.search(texto) and valor < 0 and cnpj:
        # Retencoes na fonte para servicos prestados por PJ
        # PIS+COFINS+CSLL = 4.65% para servicos (Lei 10.833/03 art.30)
        # IRRF = 1.5% para servicos profissionais
        return {
            "categoria": "RETENCAO_PJ",
            "tributo": "PIS+COFINS+CSLL (4.65%) + IRRF (1.5%) se servico",
            "aliquota_sugerida": "ate 6.15% sobre valor (se servico)",
            "valor_retencao": round(valor_abs * 0.0615, 2),
            "obs": "Pagamento a PJ - verificar se ha retencao na fonte (servico vs mercadoria)",
        }

    # PIX para PF (CPF mascarado)
    if _RX_PIX.search(texto) and valor < 0 and _RX_CPF_MASK.search(texto):
        # IRRF tabela progressiva para servico profissional autonomo
        return {
            "categoria": "RETENCAO_PF",
            "tributo": "IRRF (tabela progressiva) + INSS (11% ou 20%)",
            "aliquota_sugerida": "ate 27.5% IRRF + INSS",
            "valor_retencao": round(valor_abs * 0.075, 2),  # estimativa conservadora
            "obs": "Pagamento a PF - verificar natureza (servico, salario, dividendo)",
        }

    # TED para PJ
    if _RX_TED.search(texto) and valor < 0 and cnpj:
        return {
            "categoria": "RETENCAO_PJ",
            "tributo": "PIS+COFINS+CSLL (4.65%) + IRRF (1.5%) se servico",
            "aliquota_sugerida": "ate 6.15%",
            "valor_retencao": round(valor_abs * 0.0615, 2),
            "obs": "TED a PJ - verificar retencao",
        }

    # Compra cartao
    if _RX_CARTAO.search(texto):
        return {
            "categoria": "COMPRA_CARTAO",
            "tributo": "ICMS embutido no preco (consumidor final)",
            "aliquota_sugerida": "—",
            "valor_retencao": 0.0,
            "obs": "Compra cartao - despesa de custeio",
        }

    # Boleto
    if _RX_BOLETO.search(texto):
        return {
            "categoria": "BOLETO",
            "tributo": "PIS+COFINS+CSLL se servico (4.65%)",
            "aliquota_sugerida": "verificar natureza",
            "valor_retencao": 0.0,
            "obs": "Boleto/titulo - verificar NF de origem",
        }

    return {
        "categoria": "OUTRO",
        "tributo": "Indeterminado",
        "aliquota_sugerida": "—",
        "valor_retencao": 0.0,
        "obs": "Categoria nao identificada automaticamente",
    }
