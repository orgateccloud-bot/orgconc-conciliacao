"""Cliente da Calculadora CBS/IBS (contrato IC-02).

PRINCÍPIO (estudo de arquitetura ORGATEC): o OrgConc **orquestra, não recalcula**.
Em produção, `apurar()` chama o motor oficial (SERPRO) — hospedado ou offline,
mesmo contrato. Em dev/teste, o MODO "stub" usa uma calculadora interna
determinística com alíquotas de **PILOTO** (valores de teste, jamais apuração
oficial) para destravar o fluxo end-to-end sem depender do SERPRO (Fase 0).

Config: CALCULADORA_MODO ("stub" | "hospedada" | "offline"), CALCULADORA_BASE_URL.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from api.core import config
from api.schemas_cbs_ibs import (
    GCBS,
    GIBSMun,
    GIBSUF,
    ApuracaoCBSIBS,
    ItemApurado,
    OperacaoFiscalInput,
)

# Alíquotas de PILOTO (TESTE/TRANSIÇÃO) — espelham o exemplo IC-02. NÃO são as
# alíquotas finais da reforma; servem só ao stub local. % conforme API oficial
# (0.10 = 0,10%).
_PILOTO_P_IBS_UF = 0.10
_PILOTO_P_IBS_MUN = 0.00
_PILOTO_P_CBS = 0.10

_RESSALVA = "Valor de teste — ambiente PILOTO (alíquotas provisórias/de transição)."


def payload_hash_de(inp: OperacaoFiscalInput) -> str:
    """SHA-256 do payload de entrada CANONICALIZADO (JSON com chaves ordenadas,
    sem espaços, UTF-8). Define a regra de idempotência/auditoria do IC-02:
    produtor e consumidor DEVEM usar a mesma canonicalização."""
    canon = json.dumps(
        inp.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _round2(x: float) -> float:
    return round(x + 1e-9, 2)


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _apurar_stub(inp: OperacaoFiscalInput) -> ApuracaoCBSIBS:
    itens = inp.itens or []
    base_total = _round2(sum(i.base_calculo for i in itens))

    v_ibs_uf = _round2(base_total * _PILOTO_P_IBS_UF / 100)
    v_ibs_mun = _round2(base_total * _PILOTO_P_IBS_MUN / 100)
    v_cbs = _round2(base_total * _PILOTO_P_CBS / 100)
    v_tot = _round2(v_ibs_uf + v_ibs_mun + v_cbs)

    itens_apurados = [
        ItemApurado(
            numero=it.numero, ncm=it.ncm, cst=it.cst, cClassTrib=it.cClassTrib,
            base_calculo=it.base_calculo,
            vIBSUF=_round2(it.base_calculo * _PILOTO_P_IBS_UF / 100),
            vIBSMun=_round2(it.base_calculo * _PILOTO_P_IBS_MUN / 100),
            vCBS=_round2(it.base_calculo * _PILOTO_P_CBS / 100),
            vIS=None,
        )
        for it in itens
    ]

    base_fmt = _brl(base_total)
    return ApuracaoCBSIBS(
        documento_id=inp.documento_id,
        versao_base=config.CBS_IBS_VERSAO_BASE,
        ambiente=config.CBS_IBS_AMBIENTE,
        motor_versao="stub-interno v0 (CALCULADORA_MODO=stub)",
        uf=inp.uf,
        municipio_ibge=inp.municipio_ibge,
        data_fato_gerador=inp.data_fato_gerador,
        base_calculo_total=base_total,
        gIBSUF=GIBSUF(
            pIBSUF=_PILOTO_P_IBS_UF, vIBSUF=v_ibs_uf,
            memoriaCalculo=f"Base {base_fmt} x {_PILOTO_P_IBS_UF}% (IBS-UF) = {_brl(v_ibs_uf)}. {_RESSALVA}",
        ),
        gIBSMun=GIBSMun(
            pIBSMun=_PILOTO_P_IBS_MUN, vIBSMun=v_ibs_mun,
            memoriaCalculo=f"Base {base_fmt} x {_PILOTO_P_IBS_MUN}% (IBS-Mun) = {_brl(v_ibs_mun)}. {_RESSALVA}",
        ),
        gCBS=GCBS(
            pCBS=_PILOTO_P_CBS, vCBS=v_cbs,
            memoriaCalculo=f"Base {base_fmt} x {_PILOTO_P_CBS}% (CBS) = {_brl(v_cbs)}. {_RESSALVA}",
        ),
        gIS=None,
        vTotTrib=v_tot,
        fundamentacao_legal="LC 214/2025 — apuração CBS/IBS (stub PILOTO; sem valor oficial).",
        itens=itens_apurados or None,
        payload_hash=payload_hash_de(inp),
        obtido_em=datetime.now(timezone.utc),
    )


def _ic02_para_serpro(inp: OperacaoFiscalInput) -> dict:
    """TODO(Fase 1 — spec SERPRO): traduzir OperacaoFiscalInput → payload da
    Calculadora de Tributos (RTC). O schema exato (campos/estrutura) está na área
    do cliente cliente.serpro.gov.br — sem ele, não dá para montar o request.
    """
    raise NotImplementedError(
        "Mapeamento IC-02 → payload SERPRO pendente da spec oficial da Calculadora "
        "de Tributos (cliente.serpro.gov.br). Auth e transporte já prontos em "
        "api/services/serpro_client.py."
    )


def _serpro_para_ic02(resp: dict, inp: OperacaoFiscalInput) -> ApuracaoCBSIBS:
    """TODO(Fase 1 — spec SERPRO): achatar a resposta da Calculadora
    (objetos[].tribCalc.IBSCBS: gIBSUF/gIBSMun/gCBS/gIS) → ApuracaoCBSIBS do IC-02,
    carimbando versao_base/ambiente/motor_versao/fundamentacao (gate §4)."""
    raise NotImplementedError(
        "Parse da resposta SERPRO → ApuracaoCBSIBS pendente da spec oficial."
    )


async def apurar_via_serpro(inp: OperacaoFiscalInput) -> ApuracaoCBSIBS:
    """Orquestra a apuração no motor oficial SERPRO (Fase 1).

    Auth (token) e transporte (POST autenticado) estão prontos em serpro_client;
    o mapeamento IC-02↔SERPRO é o único pendente (spec). Levanta SerproConfigError
    se faltarem credenciais/URL, e NotImplementedError enquanto o mapeamento não
    for implementado a partir da spec.
    """
    from api.services import serpro_client

    payload = _ic02_para_serpro(inp)  # NotImplementedError até a spec
    resp = await serpro_client.chamar_calculadora(payload)
    return _serpro_para_ic02(resp, inp)


async def apurar(inp: OperacaoFiscalInput) -> ApuracaoCBSIBS:
    """Apura CBS/IBS de uma operação. Despacha por CALCULADORA_MODO.

    - "stub": calculadora interna determinística (PILOTO, sem rede). Fase 0.
    - "hospedada"/"offline": motor oficial SERPRO via serpro_client (Fase 1).
    """
    modo = config.CALCULADORA_MODO
    if modo == "stub":
        return _apurar_stub(inp)
    # Fase 1 — SERPRO-ready: auth/transporte prontos; mapeamento pendente da spec.
    return await apurar_via_serpro(inp)
