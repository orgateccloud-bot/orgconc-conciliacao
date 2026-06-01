"""P1 #5 (escopo seguro): GUIA_TRIBUTO_TIPOS como fonte única para cascata +
forensics. Testes provam que NÃO houve mudança de comportamento."""
import re

from api.matchers import cascata, forensics
from api.parsers.constants import GUIA_TRIBUTO_TIPOS


def test_canonico_tem_os_6_tipos():
    # Regressão: o conjunto canônico deve manter exatamente os tipos antigos.
    assert GUIA_TRIBUTO_TIPOS == ("DARF", "DAS", "GPS", "GNRE", "DAE", "DARJ")


def test_cascata_usa_a_fonte_unica():
    assert cascata._TRIBUTOS is GUIA_TRIBUTO_TIPOS


def test_cascata_detecta_cada_tributo():
    for tipo in GUIA_TRIBUTO_TIPOS:
        assert cascata._detecta_tributo(f"PAGAMENTO {tipo} 1234", "") == tipo
    assert cascata._detecta_tributo("PIX RECEBIDO FORNECEDOR", "") is None


def test_forensics_rx_tributo_equivalente_ao_regex_antigo():
    """Prova de não-regressão: o regex derivado casa exatamente o mesmo que o
    regex hardcoded anterior, numa bateria de amostras."""
    antigo = re.compile(r"\bDARF\b|\bDAS\b|\bGPS\b|\bGNRE\b|\bDAE\b|\bDARJ\b", re.I)
    amostras = [
        "DARF 1234", "pagamento DAS simples nacional", "GPS inss 11/2025",
        "GNRE icms interestadual", "DAE estadual", "DARJ rio de janeiro",
        "COMPRA VISA POSTO", "PIX RECEBIDO", "TARIFA MANUTENCAO",
        "DARFOO nao casa", "XDAS colado", "SEM TRIBUTO AQUI", "",
    ]
    for s in amostras:
        assert bool(antigo.search(s)) == bool(forensics._RX_TRIBUTO.search(s)), s


def test_forensics_rx_casa_todos_os_tipos():
    for tipo in GUIA_TRIBUTO_TIPOS:
        assert forensics._RX_TRIBUTO.search(f"DEB.{tipo} GUIA")
