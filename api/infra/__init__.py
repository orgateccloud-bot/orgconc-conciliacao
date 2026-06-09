"""Camada de infraestrutura.

Implementa as interfaces (Protocols) declaradas em api/domain/repositories.py
e os adapters para servicos externos (LLM, Calculadora RTC, storage, render).

REGRA: importa api/domain/, mas o inverso jamais.
"""
