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
    plano: str = Field(default="basico", max_length=20)

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
    plano: Optional[str] = Field(default=None, max_length=20)
    ativo: Optional[bool] = None

    def model_post_init(self, __context) -> None:
        if self.plano is not None and self.plano not in _PLANOS_VALIDOS:
            raise ValueError(f"Plano inválido: {self.plano}")


class LoginPayload(BaseModel):
    email: str = Field(max_length=254)
    # Sem min_length: validar tamanho no login vazaria info (senha curta -> 422
    # distinguivel de 401), quebrando a propriedade anti-enumeracao. Complexidade
    # de senha e' exigida na criacao do hash, nao no login.
    senha: str = Field(max_length=128)


# Papéis válidos de um usuário dentro da sua organização.
_ROLES_USUARIO = {"admin", "auditor", "user"}


class CriarOrgPayload(BaseModel):
    """Cria uma organização (tenant). Uso: bootstrap por admin/service."""
    nome: str = Field(max_length=255)
    cnpj: Optional[str] = None
    plano: Optional[str] = Field(default="basico", max_length=20)

    def model_post_init(self, __context) -> None:
        if self.cnpj:
            self.cnpj = re.sub(r"\D", "", self.cnpj)
            if not validar_cnpj(self.cnpj):
                raise ValueError(f"CNPJ inválido: {self.cnpj}")
        if self.plano is not None and self.plano not in _PLANOS_VALIDOS:
            raise ValueError(f"Plano inválido: {self.plano}")


class TrocarSenhaPayload(BaseModel):
    """Troca da própria senha (self-service): exige a senha atual."""
    senha_atual: str = Field(max_length=128)
    senha_nova: str = Field(min_length=8, max_length=128)


class ResetSenhaPayload(BaseModel):
    """Reset de senha de um usuário por admin/service."""
    senha_nova: str = Field(min_length=8, max_length=128)


class CriarUsuarioPayload(BaseModel):
    """Cria um usuário em uma organização. Uso: bootstrap por admin/service."""
    email: str = Field(max_length=254)
    senha: str = Field(min_length=8, max_length=128)
    org_id: str
    role: Optional[str] = "user"
    nome: Optional[str] = Field(default=None, max_length=255)

    def model_post_init(self, __context) -> None:
        if self.role is not None and self.role not in _ROLES_USUARIO:
            raise ValueError(f"Role inválido: {self.role} (use {sorted(_ROLES_USUARIO)})")
