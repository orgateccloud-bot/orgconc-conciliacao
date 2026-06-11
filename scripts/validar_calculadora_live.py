"""Validação LIVE do pipeline CBS/IBS contra a Calculadora oficial (RTC).

Exercita o caminho REAL do OrgConc (apurar_via_calculadora → calculadora_client)
contra a instância aberta do Portal RTC, com o exemplo do Manual de Serviços
RTC como gabarito: NCM 8425.31.10, CST 200, cClassTrib 200031 (redução de 60%),
base R$ 10.000,00, Porto Alegre/RS → CBS R$ 36,00 (0,36%) e IBS-UF R$ 4,00
(0,04%) na base V0033.

Uso (fora do CI — depende de rede/gov.br):
    python scripts/validar_calculadora_live.py [--base-url URL]

Sai com código 0 se TODAS as verificações passarem. Sem credencial: a API da
calculadora é aberta (posição oficial RFB: integração de volume deve usar o
componente OFFLINE self-hosted; os hosts gov.br servem p/ validação como esta).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROD_OFICIAL = "https://consumo.tributos.gov.br/servico/calcular-tributos-consumo/api"


async def main() -> int:
    ap = argparse.ArgumentParser(description="Validação live da Calculadora RTC")
    ap.add_argument("--base-url", default=PROD_OFICIAL,
                    help=f"endpoint da Calculadora (default: produção oficial {PROD_OFICIAL})")
    args = ap.parse_args()

    from api.core import config
    config.CALCULADORA_BASE_URL = args.base_url
    config.CALCULADORA_MODO = "hospedada"

    from api.schemas_cbs_ibs import ItemOperacao, OperacaoFiscalInput
    from api.services import calculadora_client
    from api.services.calculadora_cbs_ibs import apurar_via_calculadora

    falhas: list[str] = []

    def check(nome: str, cond: bool, detalhe: str = "") -> None:
        print(f"  [{'OK' if cond else 'FALHOU'}] {nome}" + (f" — {detalhe}" if detalhe else ""))
        if not cond:
            falhas.append(nome)

    print(f"== Validação live: {args.base_url}")

    # 1. Pre-flight de versão (caminho oficial dados-abertos/versao).
    versao = await calculadora_client.obter_versao_db(forcar=True)
    print(f"  versão da base reportada pelo motor: {versao}")
    check("pre-flight de versão responde", bool(versao))
    check("versão do motor == CBS_IBS_VERSAO_BASE configurada",
          versao == config.CBS_IBS_VERSAO_BASE,
          f"motor={versao} config={config.CBS_IBS_VERSAO_BASE}")

    # 2. Apuração com o exemplo do Manual RTC (gabarito público).
    inp = OperacaoFiscalInput(
        documento_id="orgconc-validacao-live",
        uf="RS",
        municipio_ibge="4314902",  # Porto Alegre
        data_fato_gerador=date(2026, 6, 1),
        itens=[ItemOperacao(numero=1, ncm="84253110", cst="200",
                            cClassTrib="200031", base_calculo=10_000.00)],
    )
    ap_res = await apurar_via_calculadora(inp)

    check("CBS = R$ 36,00 (redução de 60% sobre 0,9%)",
          abs(ap_res.gCBS.vCBS - 36.00) < 0.005, f"vCBS={ap_res.gCBS.vCBS}")
    check("IBS-UF = R$ 4,00 (redução de 60% sobre 0,1%)",
          abs(ap_res.gIBSUF.vIBSUF - 4.00) < 0.005, f"vIBSUF={ap_res.gIBSUF.vIBSUF}")
    check("base de cálculo total = R$ 10.000,00",
          abs(ap_res.base_calculo_total - 10_000.00) < 0.005,
          f"base={ap_res.base_calculo_total}")
    check("vTotTrib = CBS + IBS", abs(ap_res.vTotTrib - (36.00 + 4.00)) < 0.01,
          f"vTotTrib={ap_res.vTotTrib}")
    check("memória de cálculo presente (CBS)", bool(ap_res.gCBS.memoriaCalculo))
    check("memória cita fundamentação legal",
          "132" in (ap_res.gCBS.memoriaCalculo or "") or "LC" in (ap_res.gCBS.memoriaCalculo or ""),
          (ap_res.gCBS.memoriaCalculo or "")[:80])
    check("payload_hash carimbado", bool(ap_res.payload_hash))

    print()
    if falhas:
        print(f"RESULTADO: {len(falhas)} verificação(ões) FALHARAM: {falhas}")
        return 1
    print("RESULTADO: pipeline CBS/IBS validado AO VIVO contra a Calculadora oficial.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
