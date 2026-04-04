"""Diagnostic script for COT Momentum strategy 0-trade problem.

Counts spec_net_trend() signals at trend_weeks=3 vs trend_weeks=2
and cross-checks with price vs SMA200 filter.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.engine import init_db, session_ctx
from src.trading.backtesting.db_loader import DbDataLoader
from src.trading.backtesting.indicators import Indicators


def main() -> None:
    init_db()

    with session_ctx() as session:
        loader = DbDataLoader(session)

        instruments = loader.available_instruments()
        print(f"Available instruments: {instruments}")

        target = "EURUSD"
        if target not in instruments:
            print(f"\n{target} not in DB. Aborting.")
            return

        bars = loader.load_merged(target)
        total = len(bars)
        print(f"\n{target}: {total} merged bars")

        if total == 0:
            print("No bars loaded. Aborting.")
            return

        # Show date range
        print(f"  Date range: {bars[0].date} -> {bars[-1].date}")

        # Count bars with spec_net data
        has_cot = sum(1 for b in bars if b.spec_net is not None)
        print(f"  Bars with spec_net: {has_cot} / {total}")

        # Show spec_net value distribution
        spec_vals = [b.spec_net for b in bars if b.spec_net is not None]
        if spec_vals:
            unique_vals = len(set(spec_vals))
            print(f"  Unique spec_net values: {unique_vals}")
            print(f"  spec_net range: {min(spec_vals)} to {max(spec_vals)}")

        ind = Indicators()
        sma_period = 200

        # Iterate bars and compute signals for both trend_weeks values
        for weeks in (3, 2):
            trend_inc = 0
            trend_dec = 0
            trend_flat = 0
            trend_none = 0

            # Combined: trend + price filter
            long_signals = 0  # increasing AND price > SMA200
            short_signals = 0  # decreasing AND price < SMA200
            sma_none = 0

            # Track where signals occur for debugging
            first_long_date = None
            first_short_date = None

            for i in range(1, total + 1):
                window = bars[:i]
                trend = ind.spec_net_trend(window, weeks=weeks)

                if trend is None:
                    trend_none += 1
                elif trend == "increasing":
                    trend_inc += 1
                elif trend == "decreasing":
                    trend_dec += 1
                else:
                    trend_flat += 1

                # Check SMA200 filter
                if len(window) >= sma_period:
                    sma200 = ind.sma(window, sma_period)
                    if sma200 is None:
                        sma_none += 1
                    elif trend == "increasing" and window[-1].close > sma200:
                        long_signals += 1
                        if first_long_date is None:
                            first_long_date = window[-1].date
                    elif trend == "decreasing" and window[-1].close < sma200:
                        short_signals += 1
                        if first_short_date is None:
                            first_short_date = window[-1].date

            print(f"\n{'='*60}")
            print(f"  trend_weeks = {weeks}")
            print(f"{'='*60}")
            print(f"  spec_net_trend() results (over {total} bars):")
            print(f"    increasing : {trend_inc:>6}")
            print(f"    decreasing : {trend_dec:>6}")
            print(f"    flat       : {trend_flat:>6}")
            print(f"    None       : {trend_none:>6}")
            print()
            print(f"  Combined signals (trend + price vs SMA{sma_period}):")
            print(f"    LONG  (increasing + price>SMA200) : {long_signals:>6}")
            print(f"    SHORT (decreasing + price<SMA200) : {short_signals:>6}")
            print(f"    TOTAL actionable signals           : {long_signals + short_signals:>6}")
            if first_long_date:
                print(f"    First LONG date  : {first_long_date}")
            if first_short_date:
                print(f"    First SHORT date : {first_short_date}")

        # Bonus: check week-over-week spec_net changes to understand noise
        print(f"\n{'='*60}")
        print("  Bar-over-bar spec_net change analysis (ALL bars)")
        print(f"{'='*60}")
        cot_bars = [b for b in bars if b.spec_net is not None]
        if len(cot_bars) > 1:
            changes = []
            for i in range(1, len(cot_bars)):
                diff = cot_bars[i].spec_net - cot_bars[i - 1].spec_net
                changes.append(diff)

            up = sum(1 for c in changes if c > 0)
            down = sum(1 for c in changes if c < 0)
            flat = sum(1 for c in changes if c == 0)
            print(f"  Total bar-over-bar changes: {len(changes)}")
            print(f"    Up   (>0) : {up:>6}  ({100*up/len(changes):.1f}%)")
            print(f"    Down (<0) : {down:>6}  ({100*down/len(changes):.1f}%)")
            print(f"    Flat (=0) : {flat:>6}  ({100*flat/len(changes):.1f}%)")

            # Count consecutive streaks
            for streak_len in (2, 3, 4):
                up_streaks = 0
                down_streaks = 0
                for j in range(len(changes) - streak_len + 1):
                    window = changes[j : j + streak_len]
                    if all(c > 0 for c in window):
                        up_streaks += 1
                    if all(c < 0 for c in window):
                        down_streaks += 1
                print(
                    f"    {streak_len}-bar consecutive up: {up_streaks:>5}"
                    f"  |  down: {down_streaks:>5}"
                    f"  |  total: {up_streaks + down_streaks:>5}"
                )
        else:
            print("  Not enough COT bars for change analysis.")

        # Deduplicated analysis: only bars where spec_net actually changed
        print(f"\n{'='*60}")
        print("  Deduplicated COT-change-only analysis")
        print(f"{'='*60}")
        unique_cot_bars = []
        prev_val = None
        for b in bars:
            if b.spec_net is not None and b.spec_net != prev_val:
                unique_cot_bars.append(b)
                prev_val = b.spec_net
        print(f"  Unique COT readings (value changed): {len(unique_cot_bars)}")
        if len(unique_cot_bars) > 1:
            u_changes = []
            for i in range(1, len(unique_cot_bars)):
                diff = unique_cot_bars[i].spec_net - unique_cot_bars[i - 1].spec_net
                u_changes.append(diff)
            u_up = sum(1 for c in u_changes if c > 0)
            u_down = sum(1 for c in u_changes if c < 0)
            print(f"  Unique changes: {len(u_changes)}")
            print(f"    Up   : {u_up:>5}  ({100*u_up/len(u_changes):.1f}%)")
            print(f"    Down : {u_down:>5}  ({100*u_down/len(u_changes):.1f}%)")
            for streak_len in (2, 3, 4):
                up_s = 0
                dn_s = 0
                for j in range(len(u_changes) - streak_len + 1):
                    w = u_changes[j : j + streak_len]
                    if all(c > 0 for c in w):
                        up_s += 1
                    if all(c < 0 for c in w):
                        dn_s += 1
                print(
                    f"    {streak_len}-consecutive up: {up_s:>4}"
                    f"  |  down: {dn_s:>4}"
                    f"  |  total: {up_s + dn_s:>4}"
                )

        # Root cause: show what spec_net_trend sees for last N+1 bars
        print(f"\n{'='*60}")
        print("  ROOT CAUSE: spec_net_trend looks at ALL bars (incl. daily)")
        print(f"{'='*60}")
        print("  The function filters bars where spec_net is not None,")
        print("  then takes the last (weeks+1) bars from that list.")
        print("  Since COT is forward-filled to daily bars, consecutive")
        print("  bars have IDENTICAL spec_net values -> change=0 -> 'flat'.")
        print()
        # Show a sample window
        sample_idx = min(210, total - 1)
        sample_window = bars[:sample_idx + 1]
        relevant = [b for b in sample_window if b.spec_net is not None]
        if len(relevant) >= 4:
            last4 = relevant[-4:]
            print(f"  Example: last 4 bars with spec_net at bar index {sample_idx}:")
            for b in last4:
                print(f"    {b.date}  spec_net={b.spec_net}")
            vals = [b.spec_net for b in last4]
            changes_ex = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
            print(f"  Changes: {changes_ex}")
            print(f"  -> All zero because daily bars carry same COT value")


if __name__ == "__main__":
    main()
