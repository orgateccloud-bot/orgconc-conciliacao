"""015 — role e cliente_id no refresh_token (corrige escalada no /auth/refresh)

Antes, POST /auth/refresh reemitia o access token com role="admin" fixo — ao
introduzir login multi-usuario, qualquer sessao viraria admin apos a primeira
rotacao. Persistimos role e cliente_id da sessao no refresh_token para reemitir
o access token preservando a identidade real.

Migracao ADITIVA: ADD COLUMN com default. Linhas existentes recebem role='user'
(conservador — nao escala) e cliente_id NULL. Reversivel.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("cliente_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("refresh_tokens", "cliente_id")
    op.drop_column("refresh_tokens", "role")
