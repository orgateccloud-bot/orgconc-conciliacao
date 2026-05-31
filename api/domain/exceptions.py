"""Erros de dominio. Camadas externas mapeiam para HTTP/log/etc."""
from __future__ import annotations


class DomainError(Exception):
    """Base de erros de dominio."""


class ValorInvalido(DomainError):
    """Value object recebeu valor que viola invariante."""


class RegraViolada(DomainError):
    """Acao violou uma regra de negocio."""


class EntidadeNaoEncontrada(DomainError):
    """Lookup retornou vazio quando algo era esperado."""


class FormatoNaoSuportado(DomainError):
    """Tentativa de processar formato de arquivo desconhecido."""
