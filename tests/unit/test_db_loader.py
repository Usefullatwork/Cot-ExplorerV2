"""Unit tests for DbDataLoader — DB-backed backtesting data loader."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base, CotPosition, Instrument, PriceDaily
from src.trading.backtesting.db_loader import DbDataLoader


@pytest.fixture()
def session():
    """In-memory SQLite session with tables created."""
    eng = create_engine(
        "sqlite:///:memory:",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    factory = sessionmaker(bind=eng, autocommit=False, autoflush=False)
    sess = factory()
    yield sess
    sess.close()
    eng.dispose()


@pytest.fixture()
def loader(session):
    """DbDataLoader instance with test session."""
    return DbDataLoader(session)


@pytest.fixture()
def seed_prices(session):
    """Seed EURUSD instrument + 10 daily price rows."""
    inst = Instrument(
        key="EURUSD", name="EUR/USD", symbol="EURUSD=X",
        label="Valuta", category="valuta", class_="A", session="London",
    )
    session.add(inst)

    for i in range(10):
        day = f"2024-01-{i + 10:02d}"
        session.add(PriceDaily(
            instrument="EURUSD", date=day,
            high=1.10 + i * 0.001,
            low=1.09 + i * 0.001,
            close=1.095 + i * 0.001,
        ))
    session.commit()


@pytest.fixture()
def seed_cot(session):
    """Seed COT positions for EURUSD (CFTC code 099741)."""
    for i in range(3):
        day = f"2024-01-{i * 7 + 10:02d}"
        session.add(CotPosition(
            symbol="099741", market="EURO FX", report_type="tff",
            date=day, open_interest=500000 + i * 10000,
            spec_long=200000 + i * 5000,
            spec_short=150000 + i * 3000,
            spec_net=50000 + i * 2000,
        ))
    session.commit()


class TestAvailableInstruments:
    def test_empty_db(self, loader):
        assert loader.available_instruments() == []

    def test_with_prices(self, loader, seed_prices):
        instruments = loader.available_instruments()
        assert "EURUSD" in instruments


class TestLoadPrices:
    def test_no_data(self, loader):
        assert loader.load_prices("EURUSD") == []

    def test_returns_all_rows(self, loader, seed_prices):
        prices = loader.load_prices("EURUSD")
        assert len(prices) == 10

    def test_price_structure(self, loader, seed_prices):
        prices = loader.load_prices("EURUSD")
        p = prices[0]
        assert "date" in p
        assert "close" in p
        assert "high" in p
        assert "low" in p

    def test_case_insensitive(self, loader, seed_prices):
        prices = loader.load_prices("eurusd")
        assert len(prices) == 10


class TestLoadCot:
    def test_no_data(self, loader):
        assert loader.load_cot("EURUSD") == []

    def test_returns_cot_rows(self, loader, seed_cot):
        cot = loader.load_cot("EURUSD")
        assert len(cot) == 3

    def test_cot_structure(self, loader, seed_cot):
        cot = loader.load_cot("EURUSD")
        row = cot[0]
        assert "spec_net" in row
        assert "spec_long" in row
        assert "spec_short" in row
        assert "oi" in row

    def test_unknown_instrument(self, loader, seed_cot):
        assert loader.load_cot("UNKNOWN") == []


class TestLoadMerged:
    def test_empty_db(self, loader):
        bars = loader.load_merged("EURUSD")
        assert bars == []

    def test_prices_only(self, loader, seed_prices):
        bars = loader.load_merged("EURUSD")
        assert len(bars) == 10
        assert bars[0].instrument == "EURUSD"
        assert bars[0].price > 0

    def test_merged_with_cot(self, loader, seed_prices, seed_cot):
        bars = loader.load_merged("EURUSD")
        assert len(bars) == 10
        # At least some bars should have COT data (carried forward)
        has_cot = [b for b in bars if b.spec_net is not None]
        assert len(has_cot) > 0

    def test_date_filtering(self, loader, seed_prices):
        bars = loader.load_merged("EURUSD", start_date="2024-01-15")
        assert all(b.date >= "2024-01-15" for b in bars)

    def test_date_range_end(self, loader, seed_prices):
        bars = loader.load_merged("EURUSD", end_date="2024-01-15")
        assert all(b.date <= "2024-01-15" for b in bars)


class TestDateRange:
    def test_no_data(self, loader):
        assert loader.date_range("EURUSD") is None

    def test_with_data(self, loader, seed_prices):
        result = loader.date_range("EURUSD")
        assert result is not None
        assert result[0] == "2024-01-10"
        assert result[1] == "2024-01-19"


class TestRowCount:
    def test_no_data(self, loader):
        assert loader.row_count("EURUSD") == 0

    def test_with_data(self, loader, seed_prices):
        assert loader.row_count("EURUSD") == 10
