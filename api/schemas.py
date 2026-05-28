"""Modelos Pydantic compartilhados."""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from api.core.config import _PLANOS_VALIDOS


def validar_cnpj(cnpj: str) -> bool:
    digits = re.sub(r"\D", "", cnpj)
    if len(digits) != 14 or len(set(digits)) == 1:
        return False

    def _calc(d, pesos):
        s = sum(int(d[i]) * pesos[i] for i in range(len(pesos)))
        r = s % 11
        return 0 if r < 2 else 11 - r

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return int(digits[12]) == _calc(digits, p1) and int(digits[13]) == _calc(digits, p2)


class ClienteCreate(BaseModel):
    nome: str = Field(max_length=255)
    cnpj: Optional[str] = None
    email: Optional[str] = Field(default=None, max_length=254)
    telefone: Optional[str] = Field(default=None, max_length=30)
    plano: str = "basico"

    def model_post_init(self, __context) -> None:
        if self.cnpj:
            self.cnpj = re.sub(r"\D", "", self.cnpj)
            if not validar_cnpj(self.cnpj):
                raise ValueError(f"CNPJ inválido: {self.cnpj}")
        if self.plano not in _PLANOS_VALIDOS:
            raise ValueError(f"Plano inválido: {self.plano}")


class ClienteUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, max_length=255)
    email: Optional[str] = Field(default=None, max_length=254)
    telefone: Optional[str] = Field(default=None, max_length=30)
    plano: Optional[str] = None
    ativo: Optional[bool] = None

    def model_post_init(self, __context) -> None:
        if self.plano is not None and self.plano not in _PLANOS_VALIDOS:
            raise ValueError(f"Plano inválido: {self.plano}")


class LoginPayload(BaseModel):
    email: str = Field(max_length=254)
    senha: str = Field(min_length=8, max_length=128)
