"""Servicos de dominio — regras de negocio puras.

Recebem entidades, devolvem entidades. Sem IO, sem framework.

Para retrocompat, as funcoes legadas em api/parsers/classifier.py e
api/parsers/anomalies.py continuam expostas via api/parsers/__init__.py —
elas chamam esses servicos por baixo (a migracao acontece no Item 8).
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal
from itertools import combinations
from typing import Sequence

from api.domain.entities import Anomalia, Extrato, Severidade, Transacao


# ── Classificador contabil ─────────────────────────────────────────────────

_REGRAS_ANTES_PIX: list[tuple[tuple[str, ...], str]] = [
    (("INTERCREDIS", "TRANSF.CONTAS", "TRANSF. CONTAS", "TRANSF MESMA TIT",
      "TRANSFERENCIA MESMA TITULARIDADE", "TRANSFERENCIA ENTRE CONTAS PROPRIAS"),
     "Transferencia entre contas proprias"),
    (("DAS ", "DARF", "RFB", "INSS", "FGTS", "DAE", "GPS", "GNRE", "DAR ",
      "IRRF", "IRPJ", "CSLL", "ICMS", "ISS", "GUIA"),
     "Tributo"),
    (("IOF",), "Despesa Financeira - IOF"),
    (("JUROS", "MORA"), "Despesa Financeira - Juros"),
    (("MULTA",), "Despesa Financeira - Multa"),
    (("PAGAMENTO TD", "LIBERACAO TD", "LIBERACAO TD", "CRED.LIBERA",
      "DESCONTO TITULO", "CREDITO ROTATIVO", "ANTECIPACAO RECEBIVEL"),
     "Operacao de Credito - TD"),
    (("EMPRESTIMO", "EMPRESTIMO", "FINANCIAMENTO", "CDC", "PARCELA EMP"),
     "Pagamento de Emprestimo"),
    (("CHEQUE ESPECIAL", "LIMITE CONTA"), "Despesa Financeira - Cheque Especial"),
    (("SEGURO", "PRESTAMISTA", "PROTECAO", "PROTECAO"), "Despesa - Seguro"),
]

_REGRAS_APOS_PIX: list[tuple[tuple[str, ...], str]] = [
    (("COMPRA MASTERCARD", "COMPRA VISA", "COMPRA CARTAO", "COMPRA ELO",
      "COMPRA HIPERCARD", "COMPRA AMEX", "COMPRA DEBITO", "DEBITO COMPRA"),
     "Compra Cartao"),
    (("FATURA CARTAO", "PAGTO FATURA", "PAGAMENTO CARTAO CRED"), "Pagamento Fatura Cartao"),
    (("PEDAGIO", "PEDAGIO", "SICOOB TAG", "SEM PARAR", "MOVE MAIS", "CONECTCAR"),
     "Despesa - Pedagio"),
    (("POSTO ", "COMBUSTIVEL", "GASOLINA", "ETANOL", "DIESEL", "SHELL", "IPIRANGA"),
     "Despesa - Combustivel"),
    (("TARIFA", "MENSALIDADE", "ANUIDADE", "CESTA ", "PACOTE ", "MANUTENCAO",
      "MANUTENCAO CONTA"),
     "Despesa Bancaria - Tarifa"),
    (("BOLETO", "COBRAN", "COMPE", "COMPENSADO", "TITULO PAGO"), "Pagamento Boleto"),
    (("SALARIO", "SALARIO", "FOLHA PGTO", "PAGAMENTO FOLHA", "PROVENTO", "ADIANTAMENTO SAL"),
     "Folha de Pagamento"),
    (("PRO LABORE", "PRO-LABORE", "PRO-LABORE", "RETIRADA SOCIO"),
     "Pro-Labore / Retirada Socio"),
    (("ALUGUEL", "CONDOMINIO", "CONDOMINIO"), "Despesa - Aluguel/Condominio"),
    (("ENERGIA ELETRICA", "ENERGIA ELETRICA", "ENEL", "CEMIG", "COELBA", "COPEL",
      "CELPE", "CELESC", "ELEKTRO", "LIGHT", "EQUATORIAL"),
     "Despesa - Energia Eletrica"),
    (("AGUA", "AGUA", "SABESP", "CEDAE", "COPASA", "EMBASA", "SANEPAR"), "Despesa - Agua"),
    (("TELEFON", "VIVO", "CLARO", "OI ", "TIM ", "INTERNET", "OPERADORA"),
     "Despesa - Telecom"),
    (("SAQUE", "RETIRADA"), "Saque"),
    (("DEPOSITO", "DEPOSITO"), "Deposito em Dinheiro"),
    (("ESTORNO", "DEVOLUC"), "Estorno"),
]


def classificar(memo: str, nome: str) -> str:
    """Classificacao contabil heuristica multi-banco."""
    s = f"{memo} {nome}".upper()
    match = lambda *t: any(x in s for x in t)

    for termos, cat in _REGRAS_ANTES_PIX:
        if any(t in s for t in termos):
            return cat

    if "PIX" in s:
        if match("EMITIDO", "ENVIADO", "PAGAMENTO PIX", "PIX SAIDA", "DEBITO PIX"):
            return "Pagamento PIX - Fornecedor/Despesa"
        if match("RECEB", "CREDITO PIX", "CREDITO PIX", "PIX ENTRADA", "PIX RECEBIDO"):
            return "Receita PIX"
        return "PIX - A classificar"

    if match("TED ", "DOC "):
        if match("RECEB", "CREDITO", "CREDITO"):
            return "Receita TED/DOC"
        return "Pagamento TED/DOC"

    for termos, cat in _REGRAS_APOS_PIX:
        if any(t in s for t in termos):
            return cat

    return "A classificar"


# ── Detector de anomalias ──────────────────────────────────────────────────

_KEYWORDS_TRANSF = (
    "INTERCREDIS",
    "TRANSF.CONTAS",
    "TRANSF MESMA TIT",
    "TRANSFERENCIA ENTRE CONTAS",
)


def _eh_transferencia(t: Transacao) -> bool:
    return any(k in t.texto_busca() for k in _KEYWORDS_TRANSF)


class DetectorAnomalias:
    """Identifica padroes suspeitos em extratos.

    Heuristicas:
    - Duplicidade: mesma (data, valor, memo prefix) >=2 vezes
    - Valor alto: |valor| > 10k (atencao) ou > 50k (alerta)
    - Estorno: presenca de "ESTORNO"
    - Transferencia entre contas sem par identificado
    """

    LIMITE_ATENCAO = Decimal("10000")
    LIMITE_ALERTA = Decimal("50000")

    def analisar(self, extratos: Sequence[Extrato]) -> list[Anomalia]:
        anomalias: list[Anomalia] = []
        anomalias.extend(self._duplicidades(extratos))
        anomalias.extend(self._valores_altos(extratos))
        anomalias.extend(self._estornos(extratos))
        anomalias.extend(self._transferencias_sem_par(extratos))
        anomalias.sort(key=lambda a: (a.severidade.ordem, -abs(a.valor)))
        return anomalias

    def chaves_anomalas(self, extratos: Sequence[Extrato]) -> set[tuple[str, object, Decimal, str]]:
        """Chaves exatas das transacoes sinalizadas — usadas para marcar `eh_anomalia` na persistencia."""
        chaves: set = set()
        for e in extratos:
            contagem = Counter(
                (t.data, t.valor.quantize(Decimal("0.01")), t.memo[:40]) for t in e.transacoes
            )
            for (data, valor, memo), n in contagem.items():
                if n < 2:
                    continue
                for t in e.transacoes:
                    if t.data == data and t.valor.quantize(Decimal("0.01")) == valor and t.memo[:40] == memo:
                        chaves.add(t.chave_dedupe())

            for t in e.transacoes:
                if abs(t.valor) > self.LIMITE_ATENCAO:
                    chaves.add(t.chave_dedupe())
                if "ESTORNO" in t.texto_busca():
                    chaves.add(t.chave_dedupe())

        if len(extratos) >= 2:
            for c1, c2 in combinations(extratos, 2):
                tx1 = [t for t in c1.transacoes if _eh_transferencia(t)]
                tx2 = [t for t in c2.transacoes if _eh_transferencia(t)]
                usados: set[int] = set()
                for t1 in tx1:
                    casou = False
                    for j, t2 in enumerate(tx2):
                        if j in usados:
                            continue
                        if abs(abs(t1.valor) - abs(t2.valor)) < Decimal("0.01") and t1.valor * t2.valor < 0:
                            usados.add(j); casou = True; break
                    if not casou:
                        chaves.add(t1.chave_dedupe())
                for j, t2 in enumerate(tx2):
                    if j not in usados:
                        chaves.add(t2.chave_dedupe())
        return chaves

    # ── Heuristicas individuais ─────────────────────────────────────────────

    def _duplicidades(self, extratos: Sequence[Extrato]) -> list[Anomalia]:
        out: list[Anomalia] = []
        for e in extratos:
            contagem = Counter(
                (t.data, t.valor.quantize(Decimal("0.01")), t.memo[:40]) for t in e.transacoes
            )
            for (data, valor, memo), n in contagem.items():
                if n < 2:
                    continue
                sev = Severidade.CRITICO if n >= 3 else Severidade.ALERTA
                out.append(Anomalia(
                    severidade=sev,
                    tipo="Duplicidade",
                    titulo=f"{n}x lancamento identico em {data.isoformat()}",
                    conta=e.conta,
                    valor=valor,
                    detalhe=f"R$ {valor:,.2f} | {memo} | {n} ocorrencias",
                ))
        return out

    def _valores_altos(self, extratos: Sequence[Extrato]) -> list[Anomalia]:
        out: list[Anomalia] = []
        for e in extratos:
            for t in e.transacoes:
                v = abs(t.valor)
                memo = (t.memo or t.nome)[:60]
                if v > self.LIMITE_ALERTA:
                    out.append(Anomalia(
                        severidade=Severidade.ALERTA,
                        tipo="Valor alto",
                        titulo=f"Transacao de R$ {v:,.2f}",
                        conta=e.conta,
                        valor=t.valor,
                        detalhe=f"{t.data.isoformat()} | {memo}",
                    ))
                elif v > self.LIMITE_ATENCAO:
                    out.append(Anomalia(
                        severidade=Severidade.ATENCAO,
                        tipo="Valor alto",
                        titulo=f"Transacao de R$ {v:,.2f}",
                        conta=e.conta,
                        valor=t.valor,
                        detalhe=f"{t.data.isoformat()} | {memo}",
                    ))
        return out

    def _estornos(self, extratos: Sequence[Extrato]) -> list[Anomalia]:
        out: list[Anomalia] = []
        for e in extratos:
            for t in e.transacoes:
                if "ESTORNO" in t.texto_busca():
                    out.append(Anomalia(
                        severidade=Severidade.CRITICO,
                        tipo="Estorno",
                        titulo="Operacao estornada",
                        conta=e.conta,
                        valor=t.valor,
                        detalhe=f"{t.data.isoformat()} | R$ {t.valor:,.2f} | {t.memo[:60]}",
                    ))
        return out

    def _transferencias_sem_par(self, extratos: Sequence[Extrato]) -> list[Anomalia]:
        out: list[Anomalia] = []
        if len(extratos) < 2:
            return out
        for c1, c2 in combinations(extratos, 2):
            tx1 = [t for t in c1.transacoes if _eh_transferencia(t)]
            tx2 = [t for t in c2.transacoes if _eh_transferencia(t)]
            usados: set[int] = set()
            casados = 0
            for t1 in tx1:
                for j, t2 in enumerate(tx2):
                    if j in usados:
                        continue
                    if abs(abs(t1.valor) - abs(t2.valor)) < Decimal("0.01") and t1.valor * t2.valor < 0:
                        usados.add(j); casados += 1; break
            sem_par = (len(tx1) - casados) + (len(tx2) - casados)
            if sem_par > 0:
                out.append(Anomalia(
                    severidade=Severidade.ALERTA,
                    tipo="Transferencia sem par",
                    titulo=f"{sem_par} transferencia(s) interna(s) sem par",
                    conta=f"{c1.conta} <-> {c2.conta}",
                    valor=Decimal("0"),
                    detalhe=(
                        f"{c1.conta}: {len(tx1) - casados} sem par | "
                        f"{c2.conta}: {len(tx2) - casados} sem par"
                    ),
                ))
        return out


# Singleton conveniente para casos simples
detector_anomalias = DetectorAnomalias()
