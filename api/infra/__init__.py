"""Camada de infraestrutura.

Implementa as interfaces (Protocols) declaradas em api/domain/repositories.py
e os adapters para servicos externos (LLM, SERPRO, storage, render).

REGRA: importa api/domain/, mas o inverso jamais.
"""
