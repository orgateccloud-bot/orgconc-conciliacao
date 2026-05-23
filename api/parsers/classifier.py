from __future__ import annotations


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
    (("PAGAMENTO TD", "LIBERACAO TD", "LIBERAÇÃO TD", "CRED.LIBERA",
      "DESCONTO TITULO", "CREDITO ROTATIVO", "ANTECIPACAO RECEBIVEL"),
     "Operacao de Credito - TD"),
    (("EMPRESTIMO", "EMPRÉSTIMO", "FINANCIAMENTO", "CDC", "PARCELA EMP"),
     "Pagamento de Emprestimo"),
    (("CHEQUE ESPECIAL", "LIMITE CONTA"), "Despesa Financeira - Cheque Especial"),
    (("SEGURO", "PRESTAMISTA", "PROTECAO", "PROTEÇÃO"), "Despesa - Seguro"),
]
_REGRAS_APOS_PIX: list[tuple[tuple[str, ...], str]] = [
    (("COMPRA MASTERCARD", "COMPRA VISA", "COMPRA CARTAO", "COMPRA ELO",
      "COMPRA HIPERCARD", "COMPRA AMEX", "COMPRA DEBITO", "DEBITO COMPRA"),
     "Compra Cartao"),
    (("FATURA CARTAO", "PAGTO FATURA", "PAGAMENTO CARTAO CRED"), "Pagamento Fatura Cartao"),
    (("PEDAGIO", "PEDÁGIO", "SICOOB TAG", "SEM PARAR", "MOVE MAIS", "CONECTCAR"),
     "Despesa - Pedagio"),
    (("POSTO ", "COMBUSTIVEL", "GASOLINA", "ETANOL", "DIESEL", "SHELL", "IPIRANGA"),
     "Despesa - Combustivel"),
    (("TARIFA", "MENSALIDADE", "ANUIDADE", "CESTA ", "PACOTE ", "MANUTENCAO",
      "MANUTENÇÃO CONTA"),
     "Despesa Bancaria - Tarifa"),
    (("BOLETO", "COBRAN", "COMPE", "COMPENSADO", "TITULO PAGO"), "Pagamento Boleto"),
    (("SALARIO", "SALÁRIO", "FOLHA PGTO", "PAGAMENTO FOLHA", "PROVENTO", "ADIANTAMENTO SAL"),
     "Folha de Pagamento"),
    (("PRO LABORE", "PRÓ-LABORE", "PRO-LABORE", "RETIRADA SOCIO"),
     "Pro-Labore / Retirada Socio"),
    (("ALUGUEL", "CONDOMINIO", "CONDOMÍNIO"), "Despesa - Aluguel/Condominio"),
    (("ENERGIA ELETRICA", "ENERGIA ELÉTRICA", "ENEL", "CEMIG", "COELBA", "COPEL",
      "CELPE", "CELESC", "ELEKTRO", "LIGHT", "EQUATORIAL"),
     "Despesa - Energia Eletrica"),
    (("AGUA", "ÁGUA", "SABESP", "CEDAE", "COPASA", "EMBASA", "SANEPAR"), "Despesa - Agua"),
    (("TELEFON", "VIVO", "CLARO", "OI ", "TIM ", "INTERNET", "OPERADORA"),
     "Despesa - Telecom"),
    (("SAQUE", "RETIRADA"), "Saque"),
    (("DEPOSITO", "DEPÓSITO"), "Deposito em Dinheiro"),
    (("ESTORNO", "DEVOLUC"), "Estorno"),
]


def _classificar(memo: str, nome: str) -> str:
    """Classificacao contabil heuristica multi-banco."""
    s = f"{memo} {nome}".upper()
    match = lambda *t: any(x in s for x in t)

    for termos, cat in _REGRAS_ANTES_PIX:
        if any(t in s for t in termos):
            return cat

    if "PIX" in s:
        if match("EMITIDO", "ENVIADO", "PAGAMENTO PIX", "PIX SAIDA", "DEBITO PIX"):
            return "Pagamento PIX - Fornecedor/Despesa"
        if match("RECEB", "CREDITO PIX", "CRÉDITO PIX", "PIX ENTRADA", "PIX RECEBIDO"):
            return "Receita PIX"
        return "PIX - A classificar"

    if match("TED ", "DOC "):
        if match("RECEB", "CREDITO", "CRÉDITO"):
            return "Receita TED/DOC"
        return "Pagamento TED/DOC"

    for termos, cat in _REGRAS_APOS_PIX:
        if any(t in s for t in termos):
            return cat

    return "A classificar"
