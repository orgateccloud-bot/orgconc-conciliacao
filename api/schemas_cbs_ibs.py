"""Modelos Pydantic do contrato IC-02 — Calculadora CBS/IBS (reforma tributária).

Espelham os JSON Schemas (draft 2020-12) da fronteira Calculadora ↔ Sistemas
Fiscais:
- `OperacaoFiscalInput`  (IC-02 §3.1) — entrada (request a POST /fiscal/apurar)
- `ApuracaoCBSIBS`       (IC-02 §3.2, §4 gate, §5 memória) — saída

Os grupos de saída (gIBSUF/gIBSMun/gCBS/gIS) usam os MESMOS nomes do contrato
oficial (pIBSUF, vIBSUF, memoriaCalculo...), de modo que `model_dump(mode="json")`
valida diretamente contra `apuracao_cbs_ibs.schema.json` (teste de contrato §9.2).

Sem `gCompraGov`: o uso é empresa privada (compra governamental fora de escopo).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Entrada — OperacaoFiscalInput (IC-02 §3.1) ─────────────────────────────

class ItemOperacao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numero: int = Field(ge=1)
    ncm: Optional[str] = None
    nbs: Optional[str] = None
    cst: str = Field(pattern=r"^[0-9]{3}$")
    cClassTrib: str = Field(pattern=r"^[0-9]{6}$")
    base_calculo: float = Field(ge=0)
    quantidade: Optional[float] = Field(default=None, gt=0)
    unidade: Optional[str] = None


class OperacaoFiscalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documento_id: str
    chave: Optional[str] = Field(default=None, pattern=r"^[0-9]{44}$")
    xml_path: Optional[str] = None
    uf: str = Field(pattern=r"^[A-Z]{2}$")
    municipio_ibge: str = Field(pattern=r"^[0-9]{7}$")
    data_fato_gerador: date
    itens: Optional[list[ItemOperacao]] = None

    @model_validator(mode="after")
    def _xml_ou_itens(self) -> "OperacaoFiscalInput":
        # IC-02 §3.1: anyOf [xml_path] | [itens].
        if not self.xml_path and not self.itens:
            raise ValueError("Forneça 'xml_path' ou 'itens' (IC-02 §3.1).")
        return self


# ── Saída — ApuracaoCBSIBS (IC-02 §3.2) ────────────────────────────────────
# Grupos com os nomes EXATOS do contrato oficial (não snake_case) para o
# model_dump validar direto contra o JSON Schema.

class GIBSUF(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pIBSUF: float
    vIBSUF: float
    memoriaCalculo: str


class GIBSMun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pIBSMun: float
    vIBSMun: float
    memoriaCalculo: str


class GCBS(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pCBS: float
    vCBS: float
    memoriaCalculo: str


class GIS(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pIS: float
    vIS: float
    memoriaCalculo: str


class ItemApurado(BaseModel):
    numero: int
    ncm: Optional[str] = None
    cst: str
    cClassTrib: str
    base_calculo: float
    vIBSUF: float
    vIBSMun: float
    vCBS: float
    vIS: Optional[float] = None


class ApuracaoCBSIBS(BaseModel):
    documento_id: str
    versao_base: str
    ambiente: str
    motor_versao: Optional[str] = None
    uf: Optional[str] = None
    municipio_ibge: Optional[str] = None
    data_fato_gerador: Optional[date] = None
    base_calculo_total: float = 0.0
    gIBSUF: GIBSUF
    gIBSMun: GIBSMun
    gCBS: GCBS
    gIS: Optional[GIS] = None
    vTotTrib: float
    fundamentacao_legal: str
    itens: Optional[list[ItemApurado]] = None
    payload_hash: Optional[str] = None
    obtido_em: datetime
