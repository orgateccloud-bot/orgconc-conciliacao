"""Cliente da Calculadora CBS/IBS (contrato IC-02).

PRINCÍPIO (estudo de arquitetura ORGATEC): o OrgConc **orquestra, não recalcula**.
Em produção, `apurar()` chama a Calculadora oficial (RTC) — instância aberta do
Portal de Tributos (consumo.tributos.gov.br) ou offline local, mesmo contrato.
Em dev/teste, o MODO "stub" usa uma calculadora interna determinística com
alíquotas de **PILOTO** (valores de teste, jamais apuração oficial) para
destravar o fluxo end-to-end sem depender da rede (Fase 0).

Config: CALCULADORA_MODO ("stub" | "hospedada" | "offline"), CALCULADORA_BASE_URL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
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

log = logging.getLogger(__name__)

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
            numero=it.numero,
            ncm=it.ncm,
            cst=it.cst,
            cClassTrib=it.cClassTrib,
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
            pIBSUF=_PILOTO_P_IBS_UF,
            vIBSUF=v_ibs_uf,
            memoriaCalculo=f"Base {base_fmt} x {_PILOTO_P_IBS_UF}% (IBS-UF) = {_brl(v_ibs_uf)}. {_RESSALVA}",
        ),
        gIBSMun=GIBSMun(
            pIBSMun=_PILOTO_P_IBS_MUN,
            vIBSMun=v_ibs_mun,
            memoriaCalculo=f"Base {base_fmt} x {_PILOTO_P_IBS_MUN}% (IBS-Mun) = {_brl(v_ibs_mun)}. {_RESSALVA}",
        ),
        gCBS=GCBS(
            pCBS=_PILOTO_P_CBS,
            vCBS=v_cbs,
            memoriaCalculo=f"Base {base_fmt} x {_PILOTO_P_CBS}% (CBS) = {_brl(v_cbs)}. {_RESSALVA}",
        ),
        gIS=None,
        vTotTrib=v_tot,
        fundamentacao_legal="LC 214/2025 — apuração CBS/IBS (stub PILOTO; sem valor oficial).",
        itens=itens_apurados or None,
        payload_hash=payload_hash_de(inp),
        obtido_em=datetime.now(timezone.utc),
    )


# Endpoint da Calculadora p/ regime geral (NCM). NF-e/CT-e de transporte caem aqui.
_ENDPOINT_REGIME_GERAL = "calculadora/regime-geral"


def _num(x, *, campo: str = "") -> float:
    """A Calculadora devolve valores como string ('1000.00'); converte p/ float.

    Blindagem (#5): a Calculadora oficial pode devolver valores inesperados num
    campo numérico ('', 'N/A', None aninhado, bool, lista...). Em vez de deixar
    `float()` levantar ValueError/TypeError e derrubar a apuração com 500, trata
    como ausente (0.0) e registra log estruturado do valor problemático — o
    achado fica auditável sem quebrar o fluxo IC-02. `campo` identifica a origem
    no log (ex.: 'gIBSUF.vIBSUF').
    """
    if x is None or x == "":
        return 0.0
    # bool é subclasse de int: float(True)==1.0 silenciaria um valor inválido.
    if isinstance(x, bool):
        log.warning("Calculadora CBS/IBS: valor booleano inesperado em campo numérico "
                    "%r=%r — tratando como 0.0.", campo or "<?>", x)
        return 0.0
    try:
        v = float(x)
    except (TypeError, ValueError):
        log.warning("Calculadora CBS/IBS: valor não-numérico em campo %r=%r (tipo %s) "
                    "— tratando como 0.0.", campo or "<?>", x, type(x).__name__)
        return 0.0
    # 'inf'/'nan'/'Infinity' passam por float() mas estouram a serialização JSON
    # do router (Starlette usa allow_nan=False → 500). Trata como ausente.
    if not math.isfinite(v):
        log.warning("Calculadora CBS/IBS: valor não-finito em campo %r=%r "
                    "— tratando como 0.0.", campo or "<?>", x)
        return 0.0
    return v


def _str(x) -> str:
    """Coage campos textuais da Calculadora (cst, cClassTrib) para str.

    A Calculadora pode devolver CST/cClassTrib como int (0) ou None; passar isso
    direto a ItemApurado (campo str) levanta ValidationError → 500. Normaliza:
    None → '', restante → str(x)."""
    return "" if x is None else str(x)


def _obj(container, chave: str) -> dict:
    """Sub-objeto `chave` de um dict, SEMPRE como dict.

    Blindagem (#5/#6): `d.get(chave, {})` ainda devolve None quando a chave existe
    com valor null (`{"gIBSUF": null}`) — e o `.get()` seguinte estoura
    AttributeError, derrubando a apuração com 500. Aqui qualquer não-dict
    (None, str, lista...) vira {}, então o encadeamento de leitura é seguro."""
    if not isinstance(container, dict):
        return {}
    valor = container.get(chave)
    return valor if isinstance(valor, dict) else {}


def _memoria(grupo: dict) -> str:
    """memoriaCalculo de um grupo, SEMPRE como str (o schema IC-02 §5 exige str).

    A Calculadora pode omitir o campo ou devolvê-lo como null/número; coage p/ str
    para não quebrar a validação Pydantic da saída."""
    m = grupo.get("memoriaCalculo", "")
    return m if isinstance(m, str) else ("" if m is None else str(m))


def _ic02_para_rtc(inp: OperacaoFiscalInput) -> dict:
    """OperacaoFiscalInput (IC-02) → payload OperacaoInput da Calculadora oficial (RTC).

    Mapeamento confirmado contra o OpenAPI/resposta real (POST /calculadora/regime-geral):
    documento_id→id, municipio_ibge(str)→municipio(int), uf→uf,
    data_fato_gerador→dhFatoGerador (ISO; substitui o deprecated dataHoraEmissao),
    itens[].base_calculo→baseCalculo.
    """
    itens = []
    for it in inp.itens or []:
        item = {"numero": it.numero, "cst": it.cst, "cClassTrib": it.cClassTrib, "baseCalculo": it.base_calculo}
        if it.ncm:
            item["ncm"] = it.ncm
        if it.nbs:
            item["nbs"] = it.nbs
        if it.quantidade is not None:
            item["quantidade"] = it.quantidade
        if it.unidade:
            item["unidade"] = it.unidade
        itens.append(item)
    return {
        "id": inp.documento_id,
        "versao": config.CBS_IBS_VERSAO_BASE,
        "dhFatoGerador": f"{inp.data_fato_gerador.isoformat()}T00:00:00-03:00",
        "municipio": int(inp.municipio_ibge),
        "uf": inp.uf,
        "itens": itens,
    }


def _rtc_para_ic02(resp: dict, inp: OperacaoFiscalInput) -> ApuracaoCBSIBS:
    """Resposta ROCDomain da Calculadora oficial (RTC) → ApuracaoCBSIBS (IC-02 §3.2).

    Achata objetos[].tribCalc.IBSCBS.gIBSCBS por item; usa total.tribCalc.IBSCBSTot
    p/ os valores agregados (fallback p/ soma dos itens). Alíquotas do header vêm do
    1º item (representativo). Carimba versao_base/ambiente/motor_versao (gate §4).
    """
    objetos = resp.get("objetos") or []
    tot = _obj(_obj(resp, "total"), "tribCalc").get("IBSCBSTot") or {}
    if not isinstance(tot, dict):
        tot = {}
    por_num = {it.numero: it for it in (inp.itens or [])}

    itens_ap: list[ItemApurado] = []
    soma_uf = soma_mun = soma_cbs = soma_bc = 0.0
    rep = None  # gIBSCBS do 1º item — alíquotas representativas p/ o header
    for obj in objetos:
        if not isinstance(obj, dict):
            log.warning("Calculadora CBS/IBS: item em 'objetos' não é objeto (tipo %s) "
                        "— ignorando.", type(obj).__name__)
            continue
        ibscbs = _obj(_obj(obj, "tribCalc"), "IBSCBS")
        g = _obj(ibscbs, "gIBSCBS")
        if rep is None:
            rep = g
        v_uf = _num(_obj(g, "gIBSUF").get("vIBSUF"), campo="item.gIBSUF.vIBSUF")
        v_mun = _num(_obj(g, "gIBSMun").get("vIBSMun"), campo="item.gIBSMun.vIBSMun")
        v_cbs = _num(_obj(g, "gCBS").get("vCBS"), campo="item.gCBS.vCBS")
        bc = _num(g.get("vBC"), campo="item.vBC")
        soma_uf += v_uf
        soma_mun += v_mun
        soma_cbs += v_cbs
        soma_bc += bc
        src = por_num.get(obj.get("nObj"))
        itens_ap.append(
            ItemApurado(
                numero=obj.get("nObj") or 0,
                ncm=(src.ncm if src else None),
                cst=_str(ibscbs.get("CST")),
                cClassTrib=_str(ibscbs.get("cClassTrib")),
                base_calculo=_round2(bc),
                vIBSUF=_round2(v_uf),
                vIBSMun=_round2(v_mun),
                vCBS=_round2(v_cbs),
                vIS=None,
            )
        )

    gibs = _obj(tot, "gIBS")
    v_uf_tot = _num(_obj(gibs, "gIBSUF").get("vIBSUF"), campo="total.gIBS.gIBSUF.vIBSUF") or soma_uf
    v_mun_tot = _num(_obj(gibs, "gIBSMun").get("vIBSMun"), campo="total.gIBS.gIBSMun.vIBSMun") or soma_mun
    v_cbs_tot = _num(_obj(tot, "gCBS").get("vCBS"), campo="total.gCBS.vCBS") or soma_cbs
    base_total = _num(tot.get("vBCIBSCBS"), campo="total.vBCIBSCBS") or soma_bc
    rep = rep if isinstance(rep, dict) else {}
    return ApuracaoCBSIBS(
        documento_id=inp.documento_id,
        versao_base=config.CBS_IBS_VERSAO_BASE,
        ambiente=config.CBS_IBS_AMBIENTE,
        motor_versao=f"Calculadora oficial RTC (base {config.CBS_IBS_VERSAO_BASE})",
        uf=inp.uf,
        municipio_ibge=inp.municipio_ibge,
        data_fato_gerador=inp.data_fato_gerador,
        base_calculo_total=_round2(base_total),
        gIBSUF=GIBSUF(
            pIBSUF=_num(_obj(rep, "gIBSUF").get("pIBSUF"), campo="rep.gIBSUF.pIBSUF"),
            vIBSUF=_round2(v_uf_tot),
            memoriaCalculo=_memoria(_obj(rep, "gIBSUF")),
        ),
        gIBSMun=GIBSMun(
            pIBSMun=_num(_obj(rep, "gIBSMun").get("pIBSMun"), campo="rep.gIBSMun.pIBSMun"),
            vIBSMun=_round2(v_mun_tot),
            memoriaCalculo=_memoria(_obj(rep, "gIBSMun")),
        ),
        gCBS=GCBS(
            pCBS=_num(_obj(rep, "gCBS").get("pCBS"), campo="rep.gCBS.pCBS"),
            vCBS=_round2(v_cbs_tot),
            memoriaCalculo=_memoria(_obj(rep, "gCBS")),
        ),
        gIS=None,
        vTotTrib=_round2(v_uf_tot + v_mun_tot + v_cbs_tot),
        fundamentacao_legal="LC 214/2025 — apuração CBS/IBS via Calculadora oficial (RTC).",
        itens=itens_ap or None,
        payload_hash=payload_hash_de(inp),
        obtido_em=datetime.now(timezone.utc),
    )


async def apurar_via_calculadora(inp: OperacaoFiscalInput) -> ApuracaoCBSIBS:
    """Apura na Calculadora oficial (RTC): monta payload → chama → achata.

    Transporte em calculadora_client (instância aberta/offline, sem auth).
    Levanta CalculadoraConfigError se faltar CALCULADORA_BASE_URL.
    """
    from api.services import calculadora_client

    payload = _ic02_para_rtc(inp)
    # Pre-flight (best-effort): avisa em log se a versão da base configurada divergir
    # da que o motor reporta — não bloqueia a apuração.
    await calculadora_client.checar_versao_base()
    resp = await calculadora_client.chamar_calculadora(payload, caminho=_ENDPOINT_REGIME_GERAL)
    return _rtc_para_ic02(resp, inp)


async def apurar(inp: OperacaoFiscalInput) -> ApuracaoCBSIBS:
    """Apura CBS/IBS de uma operação. Despacha por CALCULADORA_MODO.

    - "stub": calculadora interna determinística (PILOTO, sem rede). Fase 0.
    - "hospedada"/"offline": Calculadora oficial (RTC) via calculadora_client.
    """
    modo = config.CALCULADORA_MODO
    if modo == "stub":
        return _apurar_stub(inp)
    # Transporte pronto; o mapeamento IC-02↔RTC valida contra a instância oficial.
    return await apurar_via_calculadora(inp)
