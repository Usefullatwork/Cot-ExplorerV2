"""
Cot-ExplorerV2 Backtesting Framework.

Core components:
    BacktestEngine  - Main engine that runs strategies on historical data
    Portfolio       - Tracks positions, equity, and risk
    Trade           - Represents a single trade lifecycle
    Bar             - A single data bar (price + COT)
    DataLoader      - Loads and merges price/COT data
    Indicators      - Technical indicator calculations
    Strategy        - Base class for strategy implementations

Strategies:
    COTMomentumStrategy    - COT positioning momentum + trend
    SMCConfluenceStrategy  - SMC zones + confluence score
    MacroRegimeStrategy    - VIX/DXY regime allocation
    MeanReversionStrategy  - RSI + key level mean reversion

Usage:
    from backtesting import BacktestEngine
    from backtesting.strategies import COTMomentumStrategy

    strategy = COTMomentumStrategy()
    engine = BacktestEngine(
        strategy=strategy,
        data_dir="/path/to/cot-explorer/data",
        instruments=["eurusd", "gold", "spx"],
        start_date="2020-01-01",
        end_date="2025-12-31",
    )
    results = engine.run()
"""

from .models import Trade, Portfolio, Bar
from .data_loader import DataLoader
from .indicators import Indicators
from .engine import BacktestEngine, Strategy
from . import metrics
from . import reports
from .strategies import (
    COTMomentumStrategy,
    SMCConfluenceStrategy,
    MacroRegimeStrategy,
    MeanReversionStrategy,
)

__all__ = [
    "BacktestEngine",
    "Portfolio",
    "Trade",
    "Bar",
    "DataLoader",
    "Indicators",
    "Strategy",
    "metrics",
    "reports",
    "COTMomentumStrategy",
    "SMCConfluenceStrategy",
    "MacroRegimeStrategy",
    "MeanReversionStrategy",
]
