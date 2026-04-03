"""Add wfo_runs and wfo_window_results tables for WFO persistence.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wfo_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("instrument", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("train_months", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("test_months", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("window_mode", sa.String(16), nullable=False, server_default="sliding"),
        sa.Column("total_windows", sa.Integer(), server_default="0"),
        sa.Column("total_combinations", sa.Integer(), server_default="0"),
        sa.Column("runtime_seconds", sa.Float(), nullable=True),
        sa.Column("pbo_score", sa.Float(), nullable=True),
        sa.Column("best_strategy", sa.String(64), nullable=True),
        sa.Column("best_timeframe", sa.String(8), nullable=True),
        sa.Column("best_params_json", sa.Text(), nullable=True),
        sa.Column("best_test_score", sa.Float(), nullable=True),
        sa.Column("ranking_json", sa.Text(), nullable=True),
        sa.Column("overfit_warnings_json", sa.Text(), nullable=True),
        sa.Column("oos_summary_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_wfo_runs_instrument", "wfo_runs", ["instrument"])
    op.create_index("ix_wfo_runs_started", "wfo_runs", ["started_at"])
    op.create_index("ix_wfo_runs_status", "wfo_runs", ["status"])

    op.create_table(
        "wfo_window_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("wfo_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("window_start", sa.String(10), nullable=False),
        sa.Column("window_end", sa.String(10), nullable=False),
        sa.Column("is_train", sa.Boolean(), nullable=False),
        sa.Column("strategy", sa.String(64), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("params_json", sa.Text(), nullable=True),
        sa.Column("sharpe", sa.Float(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("total_trades", sa.Integer(), server_default="0"),
        sa.Column("total_return_pct", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.create_index("ix_wfo_window_run", "wfo_window_results", ["run_id"])
    op.create_index("ix_wfo_window_strategy", "wfo_window_results", ["strategy"])
    op.create_index("ix_wfo_window_is_train", "wfo_window_results", ["is_train"])


def downgrade() -> None:
    op.drop_table("wfo_window_results")
    op.drop_table("wfo_runs")
