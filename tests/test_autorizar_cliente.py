"""Testes para api.services.auth.autorizar_cliente — multi-tenancy fiscal (F-12)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.services.auth import TokenPayload, autorizar_cliente


def test_admin_pode_acessar_qualquer_cliente():
    user = TokenPayload(sub="admin@orgatec", role="admin")
    autorizar_cliente(user, "qualquer-uuid")  # não levanta


def test_auditor_pode_acessar_qualquer_cliente():
    user = TokenPayload(sub="auditor@orgatec", role="auditor")
    autorizar_cliente(user, "qualquer-uuid")


def test_anonymous_em_dev_passa():
    user = TokenPayload(sub="anonymous", role="anonymous")
    autorizar_cliente(user, "qualquer-uuid")


def test_user_com_cliente_id_matching_passa():
    user = TokenPayload(sub="user1", role="user", cliente_id="aaa")
    autorizar_cliente(user, "aaa")


def test_user_tentando_acessar_outro_cliente_bloqueia():
    user = TokenPayload(sub="user1", role="user", cliente_id="aaa")
    with pytest.raises(HTTPException) as exc:
        autorizar_cliente(user, "bbb")
    assert exc.value.status_code == 403


def test_user_sem_cliente_id_no_token_passa():
    """Token sem cliente_id (legado): por enquanto deixa passar — TODO endurecer."""
    user = TokenPayload(sub="user1", role="user")
    autorizar_cliente(user, "qualquer-id")
