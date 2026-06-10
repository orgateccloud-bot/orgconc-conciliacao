"""Testes da descoberta automatica de modelos (api/core/model_registry.py)
e do atualizar_modelos() em config."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from api.core import config, model_registry


def _fake_model(model_id: str, iso: str, display: str | None = None):
    m = MagicMock()
    m.id = model_id
    m.created_at = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
    m.display_name = display or model_id
    return m


def test_descobrir_modelos_pega_mais_recente_por_familia():
    fake_models = [
        _fake_model("claude-fable-5", "2026-06-09", "Fable 5"),
        _fake_model("claude-fable-4", "2025-12-01", "Fable 4"),
        _fake_model("claude-sonnet-4-6", "2026-02-17", "Sonnet 4.6"),
        _fake_model("claude-haiku-4-5-20251001", "2025-10-15", "Haiku 4.5"),
    ]
    fake_client = MagicMock()
    fake_client.models.list.return_value.data = fake_models

    with patch("anthropic.Anthropic", return_value=fake_client):
        r = model_registry.descobrir_modelos("sk-ant-fake")

    assert r["fable"] == ("claude-fable-5", "Fable 5")   # mais recente, nao o Fable 4
    assert r["sonnet"][0] == "claude-sonnet-4-6"
    assert r["haiku"][0] == "claude-haiku-4-5-20251001"


def test_atualizar_modelos_atualiza_in_place():
    orig = dict(config._MODELOS_VALIDOS)
    orig_multi = list(config._MODELOS_MULTI)
    try:
        with (
            patch("api.core.config._model_registry.descobrir_modelos",
                  return_value={"fable": ("claude-fable-9", "Fable 9")}),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-x", "ORGCONC_MODELS_AUTO": "1"}),
        ):
            config.atualizar_modelos()
        assert config._MODELOS_VALIDOS["fable"] == ("claude-fable-9", "Fable 9")
        # _MODELOS_MULTI reconstruido in-place (mesma lista) refletindo o novo fable
        assert any(m[0] == "claude-fable-9" for m in config._MODELOS_MULTI)
    finally:
        config._MODELOS_VALIDOS.clear()
        config._MODELOS_VALIDOS.update(orig)
        config._MODELOS_MULTI[:] = orig_multi


def test_atualizar_modelos_desligado_por_env():
    with (
        patch.dict(os.environ, {"ORGCONC_MODELS_AUTO": "0", "ANTHROPIC_API_KEY": "sk-ant-x"}),
        patch("api.core.config._model_registry.descobrir_modelos") as mock_desc,
    ):
        config.atualizar_modelos()
        mock_desc.assert_not_called()


def test_atualizar_modelos_sem_chave_noop():
    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "", "ORGCONC_MODELS_AUTO": "1"}),
        patch("api.core.config._model_registry.descobrir_modelos") as mock_desc,
    ):
        config.atualizar_modelos(api_key="")
        mock_desc.assert_not_called()


def test_atualizar_modelos_falha_api_mantem_defaults():
    orig = dict(config._MODELOS_VALIDOS)
    with (
        patch("api.core.config._model_registry.descobrir_modelos", side_effect=RuntimeError("api down")),
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-x", "ORGCONC_MODELS_AUTO": "1"}),
    ):
        config.atualizar_modelos()  # nao deve levantar
    assert config._MODELOS_VALIDOS == orig  # defaults preservados


def test_default_fable_e_5():
    assert model_registry.DEFAULTS["fable"][0] == "claude-fable-5"
