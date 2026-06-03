"""Tradução IC-02 ↔ motor oficial SERPRO (Calculadora CBS/IBS) — Fase 1.

Isola TODA a dependência do contrato externo do SERPRO num só lugar. O resto do
OrgConc fala apenas IC-02 (api/schemas_cbs_ibs.py); este módulo converte para o
formato do motor e de volta.

⚠️  PROVISÓRIO — baseado nas SUPOSIÇÕES do estudo consolidado (nomes de campos,
    rotas, aninhamento `objetos[].tribCalc.IBSCBS`). NÃO há OpenAPI oficial ainda.
    Quando o contrato real chegar, ajuste APENAS este arquivo (mapeamento de
    nomes/rotas) e o mock do teste — o cliente e o restante do fluxo não mudam.

Mapeamentos supostos (IC-02 → SERPRO):
  documento_id        → id
  data_fato_gerador   → dataHoraEmissao (ISO-8601)
  municipio_ibge(str) → codigoMunicipio (int)
  itens[].base_calculo→ objetos[].baseCalculo
Roteamento: item com `nbs` (serviço) → /nfse/base-calculo; com `ncm`
(mercadoria) → /regime-geral.
"""
from __future__ import annotations

from datetime import datetime, timezone

from api.core import config
from api.schemas_cbs_ibs import (
    GCBS,
    GIS,
    GIBSMun,
    GIBSUF,
    ApuracaoCBSIBS,
    ItemApurado,
    OperacaoFiscalInput,
)

# Rotas supostas do motor (relativas a CALCULADORA_BASE_URL).
ROTA_REGIME_GERAL = "/regime-geral"      # mercadorias (NCM)
ROTA_NFSE = "/nfse/base-calculo"          # serviços (NBS)


class TraducaoSerproError(ValueError):
    """Resposta do SERPRO fora do formato esperado pela tradução."""


def endpoint_para(inp: OperacaoFiscalInput) -> str:
    """Roteia a operação: serviço (algum item com NBS) → NFS-e; senão mercadoria.

    Suposição: uma operação é homogênea (mercadoria OU serviço). Se houver NBS
    em qualquer item, trata como serviço.
    """
    itens = inp.itens or []
    if any(getattr(it, "nbs", None) for it in itens):
        return ROTA_NFSE
    return ROTA_REGIME_GERAL


def ic02_para_serpro(inp: OperacaoFiscalInput) -> dict:
    """Monta o payload do motor SERPRO a partir do input IC-02 (PROVISÓRIO)."""
    objetos = []
    for it in inp.itens or []:
        obj: dict = {
            "numero": it.numero,
            "cst": it.cst,
            "cClassTrib": it.cClassTrib,
            "baseCalculo": it.base_calculo,
        }
        if it.ncm:
            obj["ncm"] = it.ncm
        if it.nbs:
            obj["nbs"] = it.nbs
        if it.quantidade is not None:
            obj["quantidade"] = it.quantidade
        if it.unidade:
            obj["unidade"] = it.unidade
        objetos.append(obj)

    return {
        "id": inp.documento_id,
        "dataHoraEmissao": inp.data_fato_gerador.isoformat(),
        "uf": inp.uf,
        "codigoMunicipio": int(inp.municipio_ibge),
        "versaoBase": config.CBS_IBS_VERSAO_BASE,
        "objetos": objetos,
    }


def _grupo(d: dict, *chaves: str) -> dict:
    """Navega d[chaves...] exigindo dicts; erro claro se o formato divergir."""
    atual = d
    for k in chaves:
        if not isinstance(atual, dict) or k not in atual:
            raise TraducaoSerproError(
                f"campo ausente na resposta SERPRO: {'.'.join(chaves)}"
            )
        atual = atual[k]
    if not isinstance(atual, dict):
        raise TraducaoSerproError(f"esperado objeto em {'.'.join(chaves)}")
    return atual


def serpro_para_ic02(
    resp: dict, inp: OperacaoFiscalInput, payload_hash: str
) -> ApuracaoCBSIBS:
    """Achata a resposta do SERPRO (objetos[].tribCalc.IBSCBS) → ApuracaoCBSIBS.

    PROVISÓRIO. Agrega os valores por esfera (IBS-UF/IBS-Mun/CBS) somando os
    objetos; as alíquotas vêm do primeiro objeto (homogêneas na operação).
    """
    objetos = resp.get("objetos")
    if not isinstance(objetos, list) or not objetos:
        raise TraducaoSerproError("resposta SERPRO sem 'objetos'")

    v_ibs_uf = v_ibs_mun = v_cbs = v_is = 0.0
    base_total = 0.0
    p_ibs_uf = p_ibs_mun = p_cbs = 0.0
    tem_is = False
    itens_apurados: list[ItemApurado] = []

    for i, obj in enumerate(objetos):
        ibscbs = _grupo(obj, "tribCalc", "IBSCBS")
        g_uf = _grupo(ibscbs, "gIBSUF")
        g_mun = _grupo(ibscbs, "gIBSMun")
        g_cbs = _grupo(ibscbs, "gCBS")
        base = float(obj.get("baseCalculo", 0) or 0)
        base_total += base
        vuf = float(g_uf.get("vIBSUF", 0) or 0)
        vmun = float(g_mun.get("vIBSMun", 0) or 0)
        vcbs = float(g_cbs.get("vCBS", 0) or 0)
        v_ibs_uf += vuf
        v_ibs_mun += vmun
        v_cbs += vcbs
        if i == 0:
            p_ibs_uf = float(g_uf.get("pIBSUF", 0) or 0)
            p_ibs_mun = float(g_mun.get("pIBSMun", 0) or 0)
            p_cbs = float(g_cbs.get("pCBS", 0) or 0)
        g_is = ibscbs.get("gIS") if isinstance(ibscbs, dict) else None
        vis = float(g_is.get("vIS", 0) or 0) if isinstance(g_is, dict) else 0.0
        if vis:
            tem_is = True
            v_is += vis
        # `numero`/`ncm`/`cst`/`cClassTrib`: do input (não dependem da resposta).
        src = inp.itens[i] if inp.itens and i < len(inp.itens) else None
        itens_apurados.append(ItemApurado(
            numero=obj.get("numero", src.numero if src else i + 1),
            ncm=src.ncm if src else obj.get("ncm"),
            cst=src.cst if src else obj.get("cst", "000"),
            cClassTrib=src.cClassTrib if src else obj.get("cClassTrib", "000000"),
            base_calculo=base,
            vIBSUF=round(vuf, 2), vIBSMun=round(vmun, 2), vCBS=round(vcbs, 2),
            vIS=round(vis, 2) if vis else None,
        ))

    v_tot = round(v_ibs_uf + v_ibs_mun + v_cbs + v_is, 2)
    motor = resp.get("versaoMotor") or resp.get("motorVersao") or "SERPRO"

    return ApuracaoCBSIBS(
        documento_id=inp.documento_id,
        versao_base=resp.get("versaoBase") or config.CBS_IBS_VERSAO_BASE,
        ambiente=config.CBS_IBS_AMBIENTE,
        motor_versao=str(motor),
        uf=inp.uf,
        municipio_ibge=inp.municipio_ibge,
        data_fato_gerador=inp.data_fato_gerador,
        base_calculo_total=round(base_total, 2),
        gIBSUF=GIBSUF(pIBSUF=p_ibs_uf, vIBSUF=round(v_ibs_uf, 2),
                      memoriaCalculo=str(_grupo(objetos[0], "tribCalc", "IBSCBS")
                                         .get("gIBSUF", {}).get("memoriaCalculo", ""))),
        gIBSMun=GIBSMun(pIBSMun=p_ibs_mun, vIBSMun=round(v_ibs_mun, 2),
                        memoriaCalculo=str(_grupo(objetos[0], "tribCalc", "IBSCBS")
                                           .get("gIBSMun", {}).get("memoriaCalculo", ""))),
        gCBS=GCBS(pCBS=p_cbs, vCBS=round(v_cbs, 2),
                  memoriaCalculo=str(_grupo(objetos[0], "tribCalc", "IBSCBS")
                                     .get("gCBS", {}).get("memoriaCalculo", ""))),
        gIS=GIS(pIS=0.0, vIS=round(v_is, 2), memoriaCalculo="Imposto Seletivo (SERPRO).")
        if tem_is else None,
        vTotTrib=v_tot,
        fundamentacao_legal="LC 214/2025 — apuração CBS/IBS pelo motor oficial (SERPRO).",
        itens=itens_apurados or None,
        payload_hash=payload_hash,
        obtido_em=datetime.now(timezone.utc),
    )
