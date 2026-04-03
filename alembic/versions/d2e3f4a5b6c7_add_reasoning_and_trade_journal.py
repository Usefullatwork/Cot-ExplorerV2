"""Add reasoning_json to bot_signals and trade_journal table.

Revision ID: d2e3f4a5b6c7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa

revision = "d2e3f4a5b6c7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add reasoning_json column to bot_signals
    op.add_column("bot_signals", sa.Column("reasoning_json", sa.Text(), nullable=True))

    # Create trade_journal table
    op.create_table(
        "trade_journal",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=True),
        sa.Column("position_id", sa.Integer(), nullable=True),
        sa.Column("instrument", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("grade", sa.String(4), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("entry_reasoning", sa.Text(), nullable=True),
        sa.Column("gate_reasoning", sa.Text(), nullable=True),
        sa.Column("exit_reasoning", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=True),
        sa.Column("pnl_pips", sa.Float(), nullable=True),
        sa.Column("pnl_rr", sa.Float(), nullable=True),
        sa.Column("lessons", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["signal_id"], ["bot_signals.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["bot_positions.id"]),
    )
    op.create_index("ix_journal_instrument", "trade_journal", ["instrument"])
    op.create_index("ix_journal_created", "trade_journal", ["created_at"])
    op.create_index("ix_journal_outcome", "trade_journal", ["outcome"])


def downgrade() -> None:
    op.drop_index("ix_journal_outcome", table_name="trade_journal")
    op.drop_index("ix_journal_created", table_name="trade_journal")
    op.drop_index("ix_journal_instrument", table_name="trade_journal")
    op.drop_table("trade_journal")
    op.drop_column("bot_signals", "reasoning_json")
