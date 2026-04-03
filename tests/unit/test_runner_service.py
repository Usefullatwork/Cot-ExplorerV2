"""Unit tests for WfoRunnerService — WFO orchestration with DB persistence."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.models import Base, Instrument, PriceDaily, WfoRun, WfoWindowResult
from src.trading.backtesting.runner_service import (
    WfoRunnerService,
    _load_pepperstone_costs,
)


@pytest.fixture()
def session():
    """In-memory SQLite session with StaticPool for cross-thread visibility."""
    eng = create_engine(
        "sqlite:///:memory:",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    factory = sessionmaker(bind=eng, autocommit=False, autoflush=False, expire_on_commit=False)
    sess = factory()
    yield sess
    sess.close()
    eng.dispose()


@pytest.fixture()
def service(session):
    """WfoRunnerService with test session."""
    return WfoRunnerService(session)


def _seed_price_data(session, instrument="EURUSD", n_weeks=60):
    """Seed instrument + n_weeks of weekly price data for WFO testing.

    Generates enough data for at least one 6m train + 2m test window.
    Uses datetime arithmetic to guarantee unique dates.
    """
    from datetime import datetime, timedelta

    # Check if instrument already exists
    from sqlalchemy import select
    existing = session.execute(
        select(Instrument.key).where(Instrument.key == instrument)
    ).scalar_one_or_none()
    if not existing:
        inst = Instrument(
            key=instrument, name=instrument, symbol=f"{instrument}=X",
            label="Test", category="test", class_="A", session="London",
        )
        session.add(inst)

    base_price = 1.10 if "USD" in instrument else 2000.0
    start = datetime(2024, 1, 1)

    for i in range(n_weeks):
        d = start + timedelta(days=i * 7)
        date_str = d.strftime("%Y-%m-%d")
        noise = (i % 7 - 3) * 0.002
        price = base_price + i * 0.001 + noise

        session.add(PriceDaily(
            instrument=instrument, date=date_str,
            high=price + 0.005,
            low=price - 0.005,
            close=price,
        ))

    session.commit()


class TestLoadPepperstoneCosts:
    def test_loads_config(self):
        costs = _load_pepperstone_costs()
        # Config file exists with Pepperstone spreads
        assert isinstance(costs, dict)
        if costs:  # only if config/transaction_costs.yaml exists
            assert "EURUSD" in costs
            assert costs["EURUSD"] < 2.0  # Pepperstone spread < 2 pip


class TestWfoRunnerService:
    def test_run_wfo_no_data(self, service, session):
        """WFO run with no price data should create an error or empty run."""
        run = service.run_wfo("EURUSD")
        assert run.instrument == "EURUSD"
        assert run.status == "ok"
        assert run.total_windows == 0

    def test_run_wfo_with_data(self, service, session):
        """WFO run with sufficient data should produce results."""
        _seed_price_data(session, "EURUSD", n_weeks=60)
        run = service.run_wfo(
            "EURUSD",
            train_months=3,
            test_months=1,
            min_trades=1,  # lower threshold for test data
        )
        assert run.instrument == "EURUSD"
        assert run.status == "ok"
        assert run.finished_at is not None
        assert run.runtime_seconds > 0

    def test_run_wfo_persists_to_db(self, service, session):
        """WFO results should be persisted to wfo_runs table."""
        _seed_price_data(session, "EURUSD", n_weeks=60)
        run = service.run_wfo(
            "EURUSD",
            train_months=3,
            test_months=1,
            min_trades=1,
        )

        # Verify persisted
        from sqlalchemy import select, func

        count = session.execute(
            select(func.count(WfoRun.id))
        ).scalar()
        assert count == 1

    def test_run_all_skips_missing(self, service, session):
        """run_all should skip instruments with no price data."""
        _seed_price_data(session, "EURUSD", n_weeks=60)
        runs = service.run_all(
            instruments=["EURUSD", "NONEXISTENT"],
            train_months=3,
            test_months=1,
            min_trades=1,
        )
        # Only EURUSD should have run
        assert len(runs) == 1
        assert runs[0].instrument == "EURUSD"

    def test_pbo_score_in_range(self, service, session):
        """PBO score should be in [0, 1] when computed."""
        _seed_price_data(session, "EURUSD", n_weeks=80)
        run = service.run_wfo(
            "EURUSD",
            train_months=3,
            test_months=1,
            min_trades=1,
        )
        if run.pbo_score is not None:
            assert 0.0 <= run.pbo_score <= 1.0

    def test_ranking_json_is_list(self, service, session):
        """Ranking JSON should parse to a list."""
        _seed_price_data(session, "EURUSD", n_weeks=60)
        run = service.run_wfo(
            "EURUSD",
            train_months=3,
            test_months=1,
            min_trades=1,
        )
        if run.ranking_json:
            import json
            ranking = json.loads(run.ranking_json)
            assert isinstance(ranking, list)
