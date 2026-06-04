"""E2E do endpoint POST /fiscal/laudo/resumo (aba Auditoria Forense).

Usa um OFX SINTÉTICO (nenhum dado real de cliente) que exercita o achado
central — volume anualizado muito acima do teto EPP → regime CRITICO — e o
sinal de smurfing (3 pagamentos no mesmo dia, mesma contraparte, < R$ 10k).
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.main import app
from api.services.auth import emitir_token

client = TestClient(app)

# O /laudo/resumo dispara enriquecer_cadastro em background (BrasilAPI). Nos testes,
# trocamos por um spy no-op: evita rede e captura o enrich_all efetivamente passado.
_ENRICH_CALLS: list = []


@pytest.fixture(autouse=True)
def _spy_enriquecimento(monkeypatch):
    _ENRICH_CALLS.clear()

    async def _spy(transacoes, db=None, limite=None, enrich_all=False):
        _ENRICH_CALLS.append(enrich_all)
        return 0

    monkeypatch.setattr("api.routers.fiscal.enriquecer_cadastro", _spy)

# Período curto (5–20 jan) + volume na casa dos milhões → anualizado >> teto EPP.
# 3 PIX de < R$ 10k no mesmo dia (20/01) para o mesmo CNPJ → smurfing.
OFX_LAUDO = """OFXHEADER:100
DATA:OFXSGML
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKACCTFROM>
<ACCTID>158083-3</ACCTID>
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260105120000</DTPOSTED><TRNAMT>-2000000.00</TRNAMT><MEMO>PIX ENVIADO 11.222.333/0001-44 FORNECEDOR ALPHA</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260112120000</DTPOSTED><TRNAMT>-1500000.00</TRNAMT><MEMO>TED 11.222.333/0001-44 FORNECEDOR ALPHA</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20260115120000</DTPOSTED><TRNAMT>1200000.00</TRNAMT><MEMO>RECEBIMENTO CLIENTE BETA</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260120120000</DTPOSTED><TRNAMT>-9000.00</TRNAMT><MEMO>PIX 22.333.444/0001-55 GAMA</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260120130000</DTPOSTED><TRNAMT>-8500.00</TRNAMT><MEMO>PIX 22.333.444/0001-55 GAMA</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260120140000</DTPOSTED><TRNAMT>-9500.00</TRNAMT><MEMO>PIX 22.333.444/0001-55 GAMA</MEMO></STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>"""


def _auth():
    token = emitir_token(sub="teste@x.com", email="teste@x.com", role="admin")
    return {"Authorization": f"Bearer {token}"}


def _post_resumo(conta: str = ""):
    files = {"arquivos": ("extrato.ofx", OFX_LAUDO.encode("latin-1"), "application/x-ofx")}
    data = {"empresa_cnpj": "11222333000199", "conta": conta}
    with patch("api.main.AUTH_TOKEN", "qualquer-coisa"):
        return client.post("/fiscal/laudo/resumo", data=data, files=files, headers=_auth())


def test_laudo_resumo_estrutura_e_regime_critico():
    r = _post_resumo()
    assert r.status_code == 200, r.text
    j = r.json()

    # Identificação da empresa (CNPJ formatado a partir dos 14 dígitos passados)
    assert j["empresa"]["cnpj"] == "11.222.333/0001-99"
    assert j["conta"] is None  # conta vazia → null
    assert j["periodo"]["inicio"] == "2026-01-05"
    assert j["periodo"]["fim"] == "2026-01-20"

    # 6 transações, todas distintas (sem FITID → dedup por data/valor/memo)
    assert j["n_transacoes"] == 6

    # Achado central: anualizado >> teto EPP (R$ 4,8M) → CRITICO e incompatível
    reg = j["regime"]
    assert reg["teto"] == 4_800_000.0
    assert reg["multiplo_do_teto"] > 10
    assert reg["classe"] == "CRITICO"
    assert reg["incompativel"] is True

    # Heatmap com as 4 classes; sinais com as 3 chaves
    assert set(j["heatmap"].keys()) == {"CRITICO", "ALTO", "MEDIO", "BAIXO"}
    assert set(j["sinais"].keys()) == {"pos_baixa", "smurfing", "carrossel"}

    # Smurfing detectado (3 PIX < 10k, mesmo dia, mesma contraparte)
    assert j["sinais"]["smurfing"] >= 1

    # Top disposições: lista (capada em 20) com risk_score ordenado desc
    top = j["top_disposicoes"]
    assert isinstance(top, list) and 0 < len(top) <= 20
    scores = [d["risk_score"] for d in top]
    assert scores == sorted(scores, reverse=True)

    # CNPJs sintéticos não cacheados → background dispara enriquecimento COMPLETO.
    assert isinstance(j["enriquecimento_pendente"], int) and j["enriquecimento_pendente"] >= 1
    assert _ENRICH_CALLS == [True]


def test_laudo_resumo_filtro_conta_inexistente_400():
    r = _post_resumo(conta="999999")
    assert r.status_code == 400
    assert "conta" in r.json()["detail"].lower()


def test_laudo_resumo_exige_auth():
    files = {"arquivos": ("extrato.ofx", OFX_LAUDO.encode("latin-1"), "application/x-ofx")}
    data = {"empresa_cnpj": "11222333000199"}
    with patch("api.services.auth._LEGACY_SERVICE_TOKEN", "legacy-test-token"):
        r = client.post("/fiscal/laudo/resumo", data=data, files=files)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_enriquecer_cadastro_enrich_all_cobre_todos(monkeypatch):
    """enrich_all=True ignora CNPJ_ENRICH_LIMITE e enriquece TODOS os faltantes
    (pós-baixa fiel); sem ele, corta no top-N — o que zerava a pós-baixa no LOCAR."""
    from api.matchers import auditoria_forense as af, cnpj_enricher
    from api.matchers.cascata import Transacao

    def _tx(cnpj_fmt: str) -> Transacao:
        return Transacao(data="2026-01-01", tipo="DEBIT", valor=-100.0,
                         fitid=cnpj_fmt, memo=f"PIX {cnpj_fmt}", nome="FORN", conta="CC 1")
    txs = [_tx("11.222.333/0001-44"), _tx("22.333.444/0001-55"), _tx("33.444.555/0001-66")]

    monkeypatch.setattr(cnpj_enricher, "_carregar_cache", lambda: {})
    capturado = {}

    async def _fake_lote(faltantes, db=None):
        capturado["n"] = len(faltantes)
        return {}

    monkeypatch.setattr(cnpj_enricher, "enriquecer_lote", _fake_lote)

    assert await af.enriquecer_cadastro(txs, limite=2) == 2          # top-N corta
    assert capturado["n"] == 2
    assert await af.enriquecer_cadastro(txs, limite=2, enrich_all=True) == 3  # cobre todos
    assert capturado["n"] == 3
