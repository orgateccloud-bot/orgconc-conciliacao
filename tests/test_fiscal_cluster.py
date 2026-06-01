"""Cobertura do cluster fiscal: sefaz_distribuicao, fiscal_notifications,
fiscal_job, fiscal_persistence — via mocks (sem DB/SMTP/SEFAZ reais)."""
import asyncio
import os
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from api.services import fiscal_job as job
from api.services import fiscal_notifications as notif
from api.services import fiscal_persistence as persist
from api.services import sefaz_distribuicao as sefaz


# ── helpers ──────────────────────────────────────────────────────────────────

def _result(*, scalars_all=None, all_rows=None, scalar="__unset__"):
    res = MagicMock()
    if scalars_all is not None:
        sc = MagicMock()
        sc.all = MagicMock(return_value=scalars_all)
        res.scalars = MagicMock(return_value=sc)
    if all_rows is not None:
        res.all = MagicMock(return_value=all_rows)
    if scalar != "__unset__":
        res.scalar_one_or_none = MagicMock(return_value=scalar)
    return res


def _db(execute_return=None):
    db = AsyncMock()
    db.add = MagicMock()
    if execute_return is not None:
        db.execute = AsyncMock(return_value=execute_return)
    return db


def _session_cm():
    db = AsyncMock()
    db.add = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm), db


# ── sefaz_distribuicao ──────────────────────────────────────────────────────

def test_sefaz_baixar_not_implemented():
    r = asyncio.run(sefaz.baixar_nfes_pendentes("12345678000190", "GO", "5"))
    assert r.documentos == []
    assert r.nsu_inicial == "5" and r.nsu_final == "5"
    assert r.erro and "NOT_IMPLEMENTED" in r.erro


def test_sefaz_status_servico():
    d = asyncio.run(sefaz.consultar_status_servico("GO"))
    assert d["uf"] == "GO" and d["status"] == "STUB"


def test_sefaz_dataclasses():
    doc = sefaz.DocumentoSefaz(chave="k", nsu="1", schema="resNFe", xml_bytes=b"x")
    res = sefaz.ResultadoDistribuicao(nsu_inicial="0", nsu_final="1", documentos=[doc])
    assert res.documentos[0].chave == "k" and res.erro is None


# ── fiscal_notifications ────────────────────────────────────────────────────

def test_sanitize_header():
    assert "\n" not in notif._sanitize_header("a\nb\rc\td")
    assert notif._sanitize_header("") == ""
    assert len(notif._sanitize_header("x" * 300)) == 200


def test_smtp_config_le_env():
    with patch.dict(os.environ, {"SMTP_HOST": "h", "FISCAL_NOTIFY_EMAIL": "a@b.com"}):
        c = notif._smtp_config()
    assert c["host"] == "h" and c["to"] == "a@b.com"


def test_enviar_email_sem_config_false():
    with patch.dict(os.environ, {"SMTP_HOST": "", "FISCAL_NOTIFY_EMAIL": ""}):
        assert notif.enviar_email_alerta("s", "c") is False


def test_enviar_email_starttls_ok():
    smtp = MagicMock()
    smtp.__enter__ = MagicMock(return_value=smtp)
    smtp.__exit__ = MagicMock(return_value=False)
    with (
        patch.dict(os.environ, {"SMTP_HOST": "h", "SMTP_PORT": "587",
                                "FISCAL_NOTIFY_EMAIL": "a@b.com", "SMTP_USER": "u", "SMTP_PASS": "p"}),
        patch.object(notif.smtplib, "SMTP", return_value=smtp),
    ):
        assert notif.enviar_email_alerta("assunto", "corpo") is True
    smtp.starttls.assert_called_once()
    smtp.send_message.assert_called_once()


def test_enviar_email_ssl_465():
    smtp = MagicMock()
    smtp.__enter__ = MagicMock(return_value=smtp)
    smtp.__exit__ = MagicMock(return_value=False)
    with (
        patch.dict(os.environ, {"SMTP_HOST": "h", "SMTP_PORT": "465",
                                "FISCAL_NOTIFY_EMAIL": "a@b.com"}),
        patch.object(notif.smtplib, "SMTP_SSL", return_value=smtp),
    ):
        assert notif.enviar_email_alerta("a", "c") is True
    smtp.send_message.assert_called_once()


def test_enviar_email_excecao_false():
    with (
        patch.dict(os.environ, {"SMTP_HOST": "h", "FISCAL_NOTIFY_EMAIL": "a@b.com"}),
        patch.object(notif.smtplib, "SMTP", side_effect=OSError("boom")),
    ):
        assert notif.enviar_email_alerta("a", "c") is False


def test_notificar_classe_critica():
    db = AsyncMock()
    with (
        patch("api.services.fiscal_notifications.registrar_audit", new=AsyncMock()) as audit,
        patch("api.services.fiscal_notifications.enviar_email_alerta", return_value=True) as email,
    ):
        asyncio.run(notif.notificar_classe_critica(
            db, cliente_id="cid", cnpj_fornecedor="12345678000190",
            razao_social="Fornecedor X", risco_anual=12345.6, flags=["MEI"], classe_anterior="BAIXO",
        ))
    audit.assert_awaited_once()
    email.assert_called_once()


# ── fiscal_job ──────────────────────────────────────────────────────────────

def test_listar_clientes_ativos():
    db = _db(_result(scalars_all=["c1", "c2"]))
    assert asyncio.run(job.listar_clientes_ativos(db)) == ["c1", "c2"]


def test_detectar_mudancas_vazio():
    assert asyncio.run(job.detectar_mudancas_classe(AsyncMock(), uuid.uuid4(), [])) == []


def test_detectar_mudancas_critico():
    db = _db(_result(all_rows=[("111", "BAIXO")]))
    scores = [
        {"cnpj_fornecedor": "111", "risco_classe": "CRITICO"},
        {"cnpj_fornecedor": "222", "risco_classe": "BAIXO"},
    ]
    out = asyncio.run(job.detectar_mudancas_classe(db, uuid.uuid4(), scores))
    assert len(out) == 1
    assert out[0]["cnpj_fornecedor"] == "111" and out[0]["classe_anterior"] == "BAIXO"


def test_rodar_para_cliente():
    db = _db(_result(scalars_all=[1, 2, 3]))
    cli = SimpleNamespace(id=uuid.uuid4(), nome="X")
    out = asyncio.run(job.rodar_para_cliente(db, cli, 30))
    assert out["documentos_encontrados"] == 3 and out["janela_dias"] == 30


def test_rodar_job_sem_db():
    with patch("api.core.config.DB_DISPONIVEL", False):
        out = asyncio.run(job.rodar_job_completo())
    assert out["executado"] is False and out["motivo"] == "db_indisponivel"


def test_rodar_job_com_db():
    cli = SimpleNamespace(id=uuid.uuid4(), nome="X")
    sl, _ = _session_cm()
    with (
        patch("api.core.config.DB_DISPONIVEL", True),
        patch("api.core.config.SessionLocal", sl),
        patch("api.services.fiscal_job.listar_clientes_ativos", new=AsyncMock(return_value=[cli])),
        patch("api.services.fiscal_job.rodar_para_cliente", new=AsyncMock(return_value={"cliente_id": "x"})),
    ):
        out = asyncio.run(job.rodar_job_completo())
    assert out["executado"] is True and out["clientes_processados"] == 1


def test_rodar_job_com_db_resiliente_a_falha():
    cli = SimpleNamespace(id=uuid.uuid4(), nome="X")
    sl, _ = _session_cm()
    with (
        patch("api.core.config.DB_DISPONIVEL", True),
        patch("api.core.config.SessionLocal", sl),
        patch("api.services.fiscal_job.listar_clientes_ativos", new=AsyncMock(return_value=[cli])),
        patch("api.services.fiscal_job.rodar_para_cliente", new=AsyncMock(side_effect=RuntimeError("x"))),
    ):
        out = asyncio.run(job.rodar_job_completo())
    assert out["executado"] is True and out["clientes_processados"] == 0


# ── fiscal_persistence ──────────────────────────────────────────────────────

def test_parse_data():
    assert persist._parse_data("2026-04-15") == date(2026, 4, 15)
    assert persist._parse_data("") is None
    assert persist._parse_data("nao-data") is None


def _doc(chave, **kw):
    base = dict(
        tipo="NF-e", modelo="55", numero="1", serie="1", data_emissao="2026-04-15",
        emit_cnpj="111", emit_nome="E", emit_uf="GO", dest_cnpj="222", dest_nome="D",
        valor_total=100.0, valor_icms=0, valor_pis=0, valor_cofins=0, valor_iss=0,
        natureza_operacao="venda",
    )
    base.update(kw)
    base["chave"] = chave
    return SimpleNamespace(**base)


def test_salvar_documentos_vazio():
    assert asyncio.run(persist.salvar_documentos_fiscais(AsyncMock(), uuid.uuid4(), [])) == {}


def test_salvar_documentos_novos():
    db = _db(_result(all_rows=[]))  # nenhum existente; inserts também usam execute
    docs = [_doc("CHAVE1"), _doc("CHAVE2"), _doc("CHAVE1")]  # 3ª é duplicada no lote
    m = asyncio.run(persist.salvar_documentos_fiscais(db, uuid.uuid4(), docs))
    assert set(m.keys()) == {"CHAVE1", "CHAVE2"}
    db.flush.assert_awaited()


def test_salvar_cruzamentos():
    db = _db(_result())
    results = [
        SimpleNamespace(documento=SimpleNamespace(chave="CH"), status="CASADO",
                        diferenca_valor=0.0, diferenca_dias=0),
        SimpleNamespace(documento=None, status="SEM_NF", diferenca_valor=None, diferenca_dias=None),
    ]
    n = asyncio.run(persist.salvar_cruzamentos(db, uuid.uuid4(), results, {"CH": uuid.uuid4()}))
    assert n == 2


def test_salvar_cruzamentos_vazio():
    assert asyncio.run(persist.salvar_cruzamentos(AsyncMock(), uuid.uuid4(), [], {})) == 0


def test_listar_documentos_e_cruzamentos():
    db = _db(_result(scalars_all=["d1", "d2"]))
    assert asyncio.run(persist.listar_documentos_por_cliente(db, uuid.uuid4())) == ["d1", "d2"]
    assert asyncio.run(persist.listar_cruzamentos(db, uuid.uuid4(), status="CASADO")) == ["d1", "d2"]


def test_listar_conformidade_com_classe_minima():
    db = _db(_result(scalars_all=["c"]))
    assert asyncio.run(persist.listar_conformidade(db, uuid.uuid4(), classe_minima="ALTO")) == ["c"]


def test_salvar_conformidade_novo_critico_notifica():
    db = _db(_result(scalar=None))  # não existe -> insert
    with patch("api.services.fiscal_notifications.notificar_classe_critica", new=AsyncMock()) as notif_mock:
        out = asyncio.run(persist.salvar_conformidade(
            db, uuid.uuid4(), "12345678000190",
            {"risco_classe": "CRITICO", "razao_social": "R", "risco_tributario_anual": 1000, "flags": "MEI,X"},
        ))
    db.add.assert_called_once()
    db.flush.assert_awaited()
    notif_mock.assert_awaited_once()
    assert out.cnpj_fornecedor == "12345678000190"


def test_salvar_conformidade_existente_update_sem_notif():
    existing = MagicMock(risco_classe="MEDIO")
    db = _db(_result(scalar=existing))
    with patch("api.services.fiscal_notifications.notificar_classe_critica", new=AsyncMock()) as notif_mock:
        out = asyncio.run(persist.salvar_conformidade(
            db, uuid.uuid4(), "111", {"risco_classe": "ALTO", "razao_social": "R"},
        ))
    assert out is existing
    db.flush.assert_awaited()
    notif_mock.assert_not_awaited()  # ALTO != CRITICO
