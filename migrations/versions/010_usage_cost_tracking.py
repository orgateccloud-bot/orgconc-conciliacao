"""010 — conciliacoes: custo/tokens por conciliacao individual

Adiciona 3 colunas a `conciliacoes` para registrar o custo e o consumo de
tokens da chamada Claude de cada conciliacao especifica. Complementa o
custo diario agregado (llm_cost_daily, criada em 007) com granularidade
por operacao — permite calcular custo medio, outliers e projecoes.

Colunas:
    usage_input_tokens  INTEGER  — tokens de entrada da chamada LLM
    usage_output_tokens INTEGER  — tokens de saida
    usage_cost_usd      NUMERIC(10,6) — custo USD calculado (input + output)

IDEMPOTENTE: inspeciona o schema e so adiciona o que falta. Seguro em
ambiente novo (cria tudo) e em banco que ja tem as colunas (no-op). Rodar
online (`alembic upgrade head`).

Revision ID: 010
Revises: 009
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def _has_column(table: str, col: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(c["name"] == col for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column("conciliacoes", "usage_input_tokens"):
        op.add_column("conciliacoes", sa.Column("usage_input_tokens", sa.Integer, nullable=True))
    if not _has_column("conciliacoes", "usage_output_tokens"):
        op.add_column("conciliacoes", sa.Column("usage_output_tokens", sa.Integer, nullable=True))
    if not _has_column("conciliacoes", "usage_cost_usd"):
        op.add_column("conciliacoes", sa.Column("usage_cost_usd", sa.Numeric(10, 6), nullable=True))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("conciliacoes")}
    if "usage_cost_usd" in cols:
        op.drop_column("conciliacoes", "usage_cost_usd")
    if "usage_output_tokens" in cols:
        op.drop_column("conciliacoes", "usage_output_tokens")
    if "usage_input_tokens" in cols:
        op.drop_column("conciliacoes", "usage_input_tokens")
