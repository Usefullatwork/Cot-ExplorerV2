"""Add pipeline_state and pipeline_runs tables, extend bot_signals.

Revision ID: a1b2c3d4e5f6
Revises: 7ce832907fa1
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "7ce832907fa1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("regime", sa.String(32), nullable=True),
        sa.Column("vix_price", sa.Float(), nullable=True),
        sa.Column("var_95_pct", sa.Float(), nullable=True),
        sa.Column("var_99_pct", sa.Float(), nullable=True),
        sa.Column("cvar_95_pct", sa.Float(), nullable=True),
        sa.Column("stress_worst_pct", sa.Float(), nullable=True),
        sa.Column("stress_survives", sa.Boolean(), nullable=True),
        sa.Column("correlation_max", sa.Float(), nullable=True),
        sa.Column("open_position_count", sa.Integer(), default=0),
        sa.Column("signal_weights_json", sa.Text(), nullable=True),
        sa.Column("ensemble_quality", sa.String(16), nullable=True),
        sa.Column("kelly_cache_json", sa.Text(), nullable=True),
        sa.Column("risk_parity_json", sa.Text(), nullable=True),
        sa.Column("drift_detected", sa.Boolean(), default=False),
        sa.Column("account_equity", sa.Float(), nullable=True),
        sa.Column("peak_equity", sa.Float(), nullable=True),
        sa.Column("layer1_last_run_at", sa.DateTime(), nullable=True),
        sa.Column("layer2_last_run_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("layer", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("signals_processed", sa.Integer(), default=0),
        sa.Column("details_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_pipeline_runs_started", "pipeline_runs", ["started_at"])
    op.create_index("ix_pipeline_runs_layer", "pipeline_runs", ["layer"])

    with op.batch_alter_table("bot_signals") as batch_op:
        batch_op.add_column(sa.Column("gate_log", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("automation_level", sa.String(8), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("bot_signals") as batch_op:
        batch_op.drop_column("automation_level")
        batch_op.drop_column("gate_log")

    op.drop_index("ix_pipeline_runs_layer", "pipeline_runs")
    op.drop_index("ix_pipeline_runs_started", "pipeline_runs")
    op.drop_table("pipeline_runs")
    op.drop_table("pipeline_state")
