"""Teste com fixture OFX em disco."""
from pathlib import Path

from api.parsers import _parse_ofx

FIXTURE = Path(__file__).parent / "fixtures" / "sample.ofx"


def test_parse_fixture_ofx():
    text = FIXTURE.read_text(encoding="latin-1")
    txs = _parse_ofx(text)
    assert len(txs) == 1
    assert txs[0]["valor"] == -150.0
    assert "PIX" in txs[0]["memo"]
