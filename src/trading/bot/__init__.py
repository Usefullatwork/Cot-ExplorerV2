"""Trading bot core logic — pure functions for entry, exit, sizing, and risk."""

from src.trading.bot.config import BotSettings, LOT_PARAMS, SYMBOL_MAP
from src.trading.bot.entry_logic import evaluate_entry
from src.trading.bot.kill_switch import (
    activate_kill_switch,
    deactivate_kill_switch,
    is_kill_switch_active,
)
from src.trading.bot.lot_sizing import calculate_lot_size, get_tier_multiplier
from src.trading.bot.position_manager import manage_position

__all__ = [
    "BotSettings",
    "LOT_PARAMS",
    "SYMBOL_MAP",
    "activate_kill_switch",
    "calculate_lot_size",
    "deactivate_kill_switch",
    "evaluate_entry",
    "get_tier_multiplier",
    "is_kill_switch_active",
    "manage_position",
]
