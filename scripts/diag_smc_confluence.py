"""
Diagnostic script for SMC Confluence strategy 0-trade problem.

Investigates why the strategy produces zero trades by examining:
1. How many bars have price inside an intact supply/demand zone
2. Distribution of confluence scores across all bars
3. How many bars would trigger trades at various thresholds (6, 4, 3)
"""

import sys
from collections import Counter
from pathlib import Path

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.engine import init_db, get_session
from src.trading.backtesting.db_loader import DbDataLoader
from src.trading.backtesting.indicators import Indicators
from src.trading.backtesting.strategies.smc_confluence import SMCConfluenceStrategy


def main():
    init_db()
    session = get_session()()

    loader = DbDataLoader(session)

    # Check available instruments and row counts
    instruments = loader.available_instruments()
    print(f"Available instruments: {instruments}")
    for inst in instruments:
        rc = loader.row_count(inst)
        dr = loader.date_range(inst)
        print(f"  {inst}: {rc} rows, range={dr}")

    # Load XAUUSD merged bars
    bars = loader.load_merged("XAUUSD")
    print(f"\nXAUUSD merged bars loaded: {len(bars)}")
    if len(bars) == 0:
        print("ERROR: No bars for XAUUSD. Exiting.")
        session.close()
        return

    # Show sample bar data
    sample = bars[min(220, len(bars) - 1)]
    print(f"Sample bar at idx 220: date={sample.date}, close={sample.close}, "
          f"high={sample.high}, low={sample.low}, "
          f"spec_net={sample.spec_net}, OI={sample.open_interest}")

    # Create strategy instance with defaults
    strat = SMCConfluenceStrategy()
    ind = Indicators()

    start_idx = max(220, strat.sma_period + 1)
    print(f"\nStarting analysis from bar index {start_idx} "
          f"(date={bars[start_idx].date}) to {len(bars)-1} "
          f"(date={bars[-1].date})")
    print(f"Total bars to scan: {len(bars) - start_idx}")

    # Counters
    bars_in_demand_zone = 0
    bars_in_supply_zone = 0
    bars_in_any_zone = 0

    # Scores when price IS in a zone
    zone_long_scores = []
    zone_short_scores = []

    # Scores for ALL bars (pretending at_zone=True to see full score)
    all_long_scores = []
    all_short_scores = []

    # Trade trigger counts at various thresholds
    triggers_by_threshold = {t: {"long": 0, "short": 0} for t in [3, 4, 5, 6]}

    # Zone stats
    total_supply_zones = 0
    total_demand_zones = 0
    zone_widths_supply = []
    zone_widths_demand = []

    for i in range(start_idx, len(bars)):
        window = bars[:i + 1]
        atr = ind.atr(window, strat.atr_period)
        if not atr or atr <= 0:
            continue

        price = window[-1].close

        # Build zones
        supply_zones, demand_zones = strat._build_zones(window, atr)
        total_supply_zones = len(supply_zones)
        total_demand_zones = len(demand_zones)

        # Check if price is in any zone
        in_demand = False
        in_supply = False
        for z in demand_zones:
            zone_widths_demand.append(z["top"] - z["bottom"])
            if z["bottom"] <= price <= z["top"]:
                in_demand = True
                break

        for z in supply_zones:
            zone_widths_supply.append(z["top"] - z["bottom"])
            if z["bottom"] <= price <= z["top"]:
                in_supply = True
                break

        if in_demand:
            bars_in_demand_zone += 1
        if in_supply:
            bars_in_supply_zone += 1
        if in_demand or in_supply:
            bars_in_any_zone += 1

        # Compute confluence scores for ALL bars (at_zone=True to get
        # the full 12-factor scoring)
        long_score = strat._confluence_score(window, "long", atr, at_zone=True)
        short_score = strat._confluence_score(window, "short", atr, at_zone=True)
        all_long_scores.append(long_score)
        all_short_scores.append(short_score)

        # If in a zone, also record scores in that context
        if in_demand:
            actual_long = strat._confluence_score(window, "long", atr, at_zone=True)
            zone_long_scores.append(actual_long)
            for t in triggers_by_threshold:
                if actual_long >= t:
                    triggers_by_threshold[t]["long"] += 1

        if in_supply:
            actual_short = strat._confluence_score(window, "short", atr, at_zone=True)
            zone_short_scores.append(actual_short)
            for t in triggers_by_threshold:
                if actual_short <= -t:
                    triggers_by_threshold[t]["short"] += 1

        # Progress
        if (i - start_idx) % 50 == 0:
            pct = (i - start_idx) / (len(bars) - start_idx) * 100
            print(f"  ... processed {i - start_idx}/{len(bars) - start_idx} "
                  f"bars ({pct:.0f}%)", end="\r")

    total_scanned = len(bars) - start_idx
    print(f"\n\n{'='*70}")
    print("DIAGNOSTIC RESULTS: SMC Confluence Strategy")
    print(f"{'='*70}")

    print(f"\n--- DATA SUMMARY ---")
    print(f"Total bars scanned:  {total_scanned}")
    print(f"Date range:          {bars[start_idx].date} to {bars[-1].date}")
    print(f"Last ATR(14):        {atr:.4f}" if atr else "ATR: N/A")
    print(f"Zones at last bar:   {total_supply_zones} supply, "
          f"{total_demand_zones} demand (intact)")

    # Zone width stats
    if zone_widths_demand:
        avg_dz = sum(zone_widths_demand) / len(zone_widths_demand)
        print(f"Avg demand zone width: {avg_dz:.4f}")
    if zone_widths_supply:
        avg_sz = sum(zone_widths_supply) / len(zone_widths_supply)
        print(f"Avg supply zone width: {avg_sz:.4f}")

    print(f"\n--- ZONE HITS ---")
    print(f"Bars in demand zone: {bars_in_demand_zone} "
          f"({bars_in_demand_zone/total_scanned*100:.2f}%)")
    print(f"Bars in supply zone: {bars_in_supply_zone} "
          f"({bars_in_supply_zone/total_scanned*100:.2f}%)")
    print(f"Bars in ANY zone:    {bars_in_any_zone} "
          f"({bars_in_any_zone/total_scanned*100:.2f}%)")

    print(f"\n--- CONFLUENCE SCORE DISTRIBUTION (all bars, at_zone=True) ---")
    print(f"  Long scores (positive = bullish):")
    long_counter = Counter(all_long_scores)
    for score in sorted(long_counter.keys()):
        bar_char = "#" * min(long_counter[score], 60)
        print(f"    {score:+3d}: {long_counter[score]:5d}  {bar_char}")

    print(f"\n  Short scores (negative = bearish):")
    short_counter = Counter(all_short_scores)
    for score in sorted(short_counter.keys()):
        bar_char = "#" * min(short_counter[score], 60)
        print(f"    {score:+3d}: {short_counter[score]:5d}  {bar_char}")

    print(f"\n  Long score stats:  "
          f"min={min(all_long_scores)}, max={max(all_long_scores)}, "
          f"mean={sum(all_long_scores)/len(all_long_scores):.2f}")
    print(f"  Short score stats: "
          f"min={min(all_short_scores)}, max={max(all_short_scores)}, "
          f"mean={sum(all_short_scores)/len(all_short_scores):.2f}")

    if zone_long_scores:
        print(f"\n--- SCORES WHEN IN DEMAND ZONE ---")
        zlc = Counter(zone_long_scores)
        for score in sorted(zlc.keys()):
            print(f"    {score:+3d}: {zlc[score]:5d}")
        print(f"  max long score at demand zone: {max(zone_long_scores)}")

    if zone_short_scores:
        print(f"\n--- SCORES WHEN IN SUPPLY ZONE ---")
        zsc = Counter(zone_short_scores)
        for score in sorted(zsc.keys()):
            print(f"    {score:+3d}: {zsc[score]:5d}")
        print(f"  min short score at supply zone: {min(zone_short_scores)}")

    print(f"\n--- TRADE TRIGGERS BY THRESHOLD ---")
    print(f"  {'Threshold':>10} | {'Long (score>=T)':>16} | {'Short (score<=-T)':>18} | {'Total':>6}")
    print(f"  {'-'*10}-+-{'-'*16}-+-{'-'*18}-+-{'-'*6}")
    for t in sorted(triggers_by_threshold.keys()):
        lt = triggers_by_threshold[t]["long"]
        st = triggers_by_threshold[t]["short"]
        total = lt + st
        print(f"  {t:>10} | {lt:>16} | {st:>18} | {total:>6}")

    # Diagnosis
    print(f"\n--- DIAGNOSIS ---")
    if bars_in_any_zone == 0:
        print("PROBLEM: Price NEVER lands inside an intact zone.")
        print("  -> Zone width (ATR * 0.25) is too narrow for daily bars.")
        print("  -> Most zones get broken before price revisits them.")
    elif bars_in_any_zone < total_scanned * 0.01:
        print(f"PROBLEM: Price is in a zone only {bars_in_any_zone} bars "
              f"({bars_in_any_zone/total_scanned*100:.2f}%) -- very rare.")
        print("  -> Zone width is marginal; combined with strict confluence, "
              "near-zero trades.")

    t6 = triggers_by_threshold[6]["long"] + triggers_by_threshold[6]["short"]
    t4 = triggers_by_threshold[4]["long"] + triggers_by_threshold[4]["short"]
    t3 = triggers_by_threshold[3]["long"] + triggers_by_threshold[3]["short"]
    print(f"\nAt threshold 6 (default): {t6} trades possible")
    print(f"At threshold 4:           {t4} trades possible")
    print(f"At threshold 3:           {t3} trades possible")

    if t6 == 0 and t4 == 0:
        print("\nCONCLUSION: Even at threshold 4, zero trades. The zone filter "
              "alone is the primary bottleneck.")
        print("RECOMMENDATION: Widen zone_atr_buffer from 0.25 to 0.5-1.0 AND "
              "reduce min_confluence to 3-4.")
    elif t6 == 0 and t4 > 0:
        print(f"\nCONCLUSION: The min_confluence=6 threshold is too strict. "
              f"Lowering to 4 would yield {t4} trades.")
        print("RECOMMENDATION: Reduce min_confluence to 4.")
    else:
        print(f"\nThreshold 6 yields {t6} trades -- strategy should work. "
              "Check the backtest engine for bugs.")

    session.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
