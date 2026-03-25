"""
Backtesting strategies for Cot-ExplorerV2.

Available strategies:
    COTMomentumStrategy    - COT positioning + trend following
    SMCConfluenceStrategy  - SMC zones + confluence score filter
    MacroRegimeStrategy    - VIX/DXY regime-based allocation
    MeanReversionStrategy  - Mean reversion at key S/D levels
"""

from .cot_momentum import COTMomentumStrategy
from .smc_confluence import SMCConfluenceStrategy
from .macro_regime import MacroRegimeStrategy
from .mean_reversion import MeanReversionStrategy

__all__ = [
    "COTMomentumStrategy",
    "SMCConfluenceStrategy",
    "MacroRegimeStrategy",
    "MeanReversionStrategy",
]
