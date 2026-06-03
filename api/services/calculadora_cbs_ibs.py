"""Cliente da Calculadora CBS/IBS (serviço OrgFiscal) — STUB / seam de integração.

Fronteira do IC-02: o OrgConc é CONSUMIDOR; o cálculo vive na Calculadora, sobre
a API oficial do SERPRO/RFB (CalculadorTributo). Este módulo define o contrato de
chamada e devolve um dict no formato de `ApuracaoCBSIBS` (pronto para
`api.services.fiscal_persistence.salvar_apuracao`).

⚠️ NÃO IMPLEMENTADO: o serviço OrgFiscal ainda não existe. As funções abaixo
documentam o contrato (IC-02 §3) e levantam NotImplementedError. Quando o serviço
subir (POST /apurar), implementar a chamada HTTP AQUI — e só aqui (ponto único de
troca entre API hospedada e back-end offline, IC-02 §2).
"""
from __future__ import annotations

import uuid
from typing import Optional

# Flag explícita para o call-site checar antes de apurar (e p/ localizar via grep).
ORGFISCAL_DISPONIVEL = False


async def apurar_documento(
    *,
    documento_id: uuid.UUID,
    xml_path: Optional[str],
    uf: Optional[str] = None,
    municipio_ibge: Optional[str] = None,
    data_fato_gerador: Optional[str] = None,
) -> dict:
    """Apura CBS/IBS/IS de um documento fiscal via Calculadora (IC-02 §3).

    Entrada mínima: `xml_path` — a Calculadora reprocessa o XML para obter os
    itens (NCM/CST/base), cf. IC-02 §8.2. Saída: dict no formato de
    `ApuracaoCBSIBS` (versao_base, ambiente, valores/alíquotas por esfera,
    v_tot_trib, memoria_calculo, itens, fundamentacao_legal, motor_versao),
    pronto para `salvar_apuracao`.

    TODO(OrgFiscal): implementar a chamada HTTP ao endpoint POST /apurar.
    Carimbar SEMPRE `versao_base` e `ambiente` (gate IC-02 §4). Em PILOTO, o
    consumidor deve propagar a ressalva de provisoriedade (IC-02 §4.2).
    """
    raise NotImplementedError(
        "Calculadora CBS/IBS (OrgFiscal) ainda nao disponivel — ver IC-02 §8.2. "
        "Implementar a chamada HTTP ao endpoint /apurar quando o servico subir."
    )
