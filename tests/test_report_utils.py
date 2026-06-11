"""Testes para api/services/report_utils.py — formatação pt-BR e CSS de fontes."""
from __future__ import annotations

import pytest


# ── format_brl ────────────────────────────────────────────────────────────────

def test_format_brl_inteiro():
    from api.services.report_utils import format_brl
    assert format_brl(1234567.89) == "1.234.567,89"


def test_format_brl_zero():
    from api.services.report_utils import format_brl
    assert format_brl(0) == "0,00"


def test_format_brl_pequeno():
    from api.services.report_utils import format_brl
    assert format_brl(1.5) == "1,50"


def test_format_brl_negativo_sem_sinal():
    """Negativo sem sinal: retorna valor absoluto (o sinal fica no contexto)."""
    from api.services.report_utils import format_brl
    assert format_brl(-500.0) == "500,00"


def test_format_brl_none():
    from api.services.report_utils import format_brl
    assert format_brl(None) == "—"


def test_format_brl_sem_virgula_en_us():
    """Não deve ter vírgula como separador de milhar (padrão en-US)."""
    from api.services.report_utils import format_brl
    resultado = format_brl(1234567.89)
    assert "," not in resultado.replace(",89", "")  # vírgula só nos decimais


# ── format_num ───────────────────────────────────────────────────────────────

def test_format_num_inteiro():
    from api.services.report_utils import format_num
    assert format_num(1234567) == "1.234.567"


def test_format_num_zero():
    from api.services.report_utils import format_num
    assert format_num(0) == "0"


def test_format_num_com_decimais():
    from api.services.report_utils import format_num
    assert format_num(1234.5, decimais=2) == "1.234,50"


# ── format_pct ───────────────────────────────────────────────────────────────

def test_format_pct_normal():
    from api.services.report_utils import format_pct
    assert format_pct(0.123) == "12,3%"


def test_format_pct_zero():
    from api.services.report_utils import format_pct
    assert format_pct(0.0) == "0,0%"


# ── TOKENS ───────────────────────────────────────────────────────────────────

def test_tokens_paleta():
    from api.services.report_utils import TOKENS
    assert TOKENS["paleta"]["navy"] == "#1A3A6B"
    assert TOKENS["paleta"]["blue"] == "#5BA9D6"


def test_tokens_severidade():
    from api.services.report_utils import TOKENS
    crit = TOKENS["severidade"]["CRITICO"]
    assert crit["bg"] == "#FEE2E2"
    assert crit["texto"] == "#991B1B"


# ── font_faces_css ───────────────────────────────────────────────────────────

def test_font_faces_css_contem_fontes():
    from api.services.report_utils import font_faces_css
    css = font_faces_css()
    if not css:
        pytest.skip("Fontes ausentes em api/assets/fonts/")
    assert "@font-face" in css
    assert "Manrope" in css
    assert "Instrument Serif" in css
    assert "JetBrains Mono" in css


def test_font_faces_css_sem_urls_externas():
    """Garante que o CSS não tenta buscar fontes da internet (anti-SSRF)."""
    from api.services.report_utils import font_faces_css
    css = font_faces_css()
    if not css:
        pytest.skip("Fontes ausentes em api/assets/fonts/")
    assert "googleapis.com" not in css
    assert "fonts.gstatic.com" not in css
    assert "http://" not in css
    assert "https://" not in css


def test_font_faces_css_usa_data_uri():
    """CSS usa data-URI para fontes — compatível com url_fetcher bloqueante do WeasyPrint."""
    from api.services.report_utils import font_faces_css
    css = font_faces_css()
    if not css:
        pytest.skip("Fontes ausentes em api/assets/fonts/")
    assert "data:font/woff2;base64," in css


def test_font_faces_css_cacheado():
    """Chamadas repetidas retornam o mesmo objeto (cache de módulo)."""
    from api.services.report_utils import font_faces_css
    css1 = font_faces_css()
    css2 = font_faces_css()
    assert css1 is css2
