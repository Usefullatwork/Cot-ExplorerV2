"""Diagnostic script for the Macro Regime Strategy 0-trade bug.

Confirms that UPPERCASE instrument keys from the WFO runner never match
the LOWERCASE keys in ASSET_REGIME_DIR, RISK_ON_ASSETS, RISK_OFF_ASSETS,
and the hardcoded VIX/DXY proxy lookups inside on_bar().
"""

import sys
from pathlib import Path

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.engine import init_db, session_ctx
from src.trading.backtesting.db_loader import DbDataLoader
from src.trading.backtesting.strategies.macro_regime import (
    ASSET_REGIME_DIR,
    RISK_OFF_ASSETS,
    RISK_ON_ASSETS,
    MacroRegimeStrategy,
)

SEPARATOR = "=" * 72


def main():
    init_db()

    with session_ctx() as session:
        loader = DbDataLoader(session)

        # ── 1. Show available instruments (UPPERCASE from DB) ──
        instruments = loader.available_instruments()
        print(SEPARATOR)
        print("1. AVAILABLE INSTRUMENTS IN DB (as returned by DbDataLoader)")
        print(SEPARATOR)
        for inst in instruments:
            print(f"   {inst!r}")
        print()

        # ── 2. Primary bug: ASSET_REGIME_DIR key case mismatch ──
        print(SEPARATOR)
        print("2. ASSET_REGIME_DIR LOOKUP WITH UPPERCASE KEYS (the primary bug)")
        print(SEPARATOR)
        print()
        print(f"   ASSET_REGIME_DIR keys: {sorted(ASSET_REGIME_DIR.keys())}")
        print()

        test_keys = ["SPX", "EURUSD", "GOLD", "DXY", "spx", "eurusd", "gold", "dxy"]
        for key in test_keys:
            result = ASSET_REGIME_DIR.get(key)
            match = "MATCH" if result is not None else "MISS --> continue (skipped)"
            print(f"   ASSET_REGIME_DIR.get({key!r:12s}) = {str(result):6s}  [{match}]")

        print()
        print("   CONCLUSION: ALL uppercase lookups return None.")
        print("   Line 213-214 in macro_regime.py: `if asset_dir is None: continue`")
        print("   skips every instrument --> 0 trades.")
        print()

        # ── 3. Secondary bug: VIX proxy lookup uses lowercase ──
        print(SEPARATOR)
        print("3. VIX PROXY LOOKUP (secondary bug, lines 167-169)")
        print(SEPARATOR)
        print()
        print('   Code: for vix_proxy in ["spx", "nas100"]:')
        print('             if vix_proxy in bars_by_instrument: ...')
        print()

        # Simulate the WFO bars_by_instrument dict with UPPERCASE keys
        sample_keys_upper = ["SPX", "NAS100", "EURUSD", "DXY", "GOLD"]
        fake_bars_by_inst = {k: [] for k in sample_keys_upper}

        for proxy in ["spx", "nas100"]:
            found = proxy in fake_bars_by_inst
            print(f"   {proxy!r} in bars_by_instrument(UPPER keys) = {found}")

        print()
        print("   CONCLUSION: VIX estimation always falls back to default 20.0")
        print()

        # ── 4. Secondary bug: DXY instrument lookup uses lowercase ──
        print(SEPARATOR)
        print("4. DXY INSTRUMENT LOOKUP (secondary bug, line 174)")
        print(SEPARATOR)
        print()
        strategy = MacroRegimeStrategy()
        print(f"   self.dxy_instrument = {strategy.dxy_instrument!r}")
        found = strategy.dxy_instrument in fake_bars_by_inst
        print(f"   {strategy.dxy_instrument!r} in bars_by_instrument(UPPER keys) = {found}")
        print()
        print("   CONCLUSION: DXY trend always stays 'flat' (never reads DXY bars)")
        print()

        # ── 5. RISK_ON_ASSETS / RISK_OFF_ASSETS membership ──
        print(SEPARATOR)
        print("5. RISK ASSET SET MEMBERSHIP (secondary bug, lines 221-224)")
        print(SEPARATOR)
        print()
        print(f"   RISK_ON_ASSETS:  {sorted(RISK_ON_ASSETS)}")
        print(f"   RISK_OFF_ASSETS: {sorted(RISK_OFF_ASSETS)}")
        print()
        for key in ["SPX", "GOLD", "EURUSD"]:
            on = key in RISK_ON_ASSETS
            off = key in RISK_OFF_ASSETS
            print(f"   {key!r:10s} in RISK_ON={on}, in RISK_OFF={off}")
        print()
        print("   CONCLUSION: Even if ASSET_REGIME_DIR matched, the risk-off branch")
        print("   would never flip directions because UPPERCASE keys miss these sets too.")
        print()

        # ── 6. Load real SPX data and test _estimate_vix ──
        print(SEPARATOR)
        print("6. VIX ESTIMATION FROM REAL SPX DATA")
        print(SEPARATOR)
        print()

        spx_bars = loader.load_merged("SPX")
        spx_count = len(spx_bars)
        print(f"   SPX bars loaded: {spx_count}")

        if spx_count > 25:
            vix_est = strategy._estimate_vix(spx_bars, 20)
            print(f"   _estimate_vix(SPX bars, period=20) = {vix_est:.2f}")
            print(f"   Reasonable range (10-40)? {'YES' if 10 <= vix_est <= 40 else 'NO -- out of range'}")

            # Show a few windows
            print()
            print("   VIX estimates at 3-month intervals:")
            step = max(1, spx_count // 8)
            for idx in range(25, spx_count, step):
                window = spx_bars[:idx]
                v = strategy._estimate_vix(window, 20)
                print(f"     [{window[-1].date}]  vix_est = {v:.2f}")
        else:
            print("   NOT ENOUGH SPX BARS -- skipping VIX test")
        print()

        # ── 7. Load real DXY data and test _dxy_trend ──
        print(SEPARATOR)
        print("7. DXY TREND DETECTION FROM REAL DXY DATA")
        print(SEPARATOR)
        print()

        dxy_bars = loader.load_merged("DXY")
        dxy_count = len(dxy_bars)
        print(f"   DXY bars loaded: {dxy_count}")

        if dxy_count > 10:
            trend = strategy._dxy_trend(dxy_bars, strategy.dxy_lookback)
            print(f"   _dxy_trend(DXY bars, lookback={strategy.dxy_lookback}) = {trend!r}")

            last = dxy_bars[-1].close
            prev = dxy_bars[-(strategy.dxy_lookback + 1)].close
            chg = last / prev - 1
            print(f"   Last close: {last:.4f}, {strategy.dxy_lookback}-bar ago: {prev:.4f}")
            print(f"   Change: {chg*100:.3f}%  (threshold: +/-0.5%)")

            # Show trend at several points
            print()
            print("   DXY trend at 3-month intervals:")
            step = max(1, dxy_count // 8)
            for idx in range(10, dxy_count, step):
                window = dxy_bars[:idx]
                t = strategy._dxy_trend(window, strategy.dxy_lookback)
                print(f"     [{window[-1].date}]  trend = {t!r}")
        else:
            print("   NOT ENOUGH DXY BARS -- skipping trend test")
        print()

        # ── 8. Simulate _classify_regime for each month ──
        print(SEPARATOR)
        print("8. REGIME CLASSIFICATION ACROSS MONTHS (simulated)")
        print(SEPARATOR)
        print()

        if spx_count > 25 and dxy_count > 10:
            # Build month index from SPX dates
            months_seen = set()
            month_indices = []
            for i, bar in enumerate(spx_bars):
                m = bar.date[:7]
                if m not in months_seen and i >= 25:
                    months_seen.add(m)
                    month_indices.append(i)

            print(f"   {'Month':>10s}  {'VIX Est':>8s}  {'DXY Trend':>14s}  {'Regime':>10s}")
            print(f"   {'-'*10}  {'-'*8}  {'-'*14}  {'-'*10}")

            for idx in month_indices[:24]:  # first 24 months
                spx_window = spx_bars[:idx]
                vix = strategy._estimate_vix(spx_window, 20)

                # Find DXY bars up to same date
                target_date = spx_bars[idx].date
                dxy_window = [b for b in dxy_bars if b.date <= target_date]

                if len(dxy_window) > strategy.dxy_lookback:
                    dxy_t = strategy._dxy_trend(dxy_window, strategy.dxy_lookback)
                else:
                    dxy_t = "flat"

                regime = strategy._classify_regime(vix, dxy_t)
                print(f"   {target_date[:7]:>10s}  {vix:>8.2f}  {dxy_t:>14s}  {regime:>10s}")
        else:
            print("   NOT ENOUGH DATA -- skipping regime simulation")
        print()

        # ── 9. _should_rebalance check ──
        print(SEPARATOR)
        print("9. REBALANCE TRIGGER (_should_rebalance)")
        print(SEPARATOR)
        print()

        strat2 = MacroRegimeStrategy()
        test_dates = [
            "2024-01-05", "2024-01-12", "2024-01-19",
            "2024-02-02", "2024-02-09",
            "2024-03-01",
        ]
        for d in test_dates:
            result = strat2._should_rebalance(d)
            print(f"   _should_rebalance({d!r}) = {result}  (month state: {strat2._last_rebalance_month!r})")
        print()
        print("   CONCLUSION: Triggers correctly on first bar of each new month.")
        print()

        # ── 10. Full on_bar simulation showing 0 actions ──
        print(SEPARATOR)
        print("10. FULL on_bar() SIMULATION WITH UPPERCASE KEYS --> 0 ACTIONS")
        print(SEPARATOR)
        print()

        if spx_count > 30:
            from src.trading.backtesting.models import Portfolio

            strat3 = MacroRegimeStrategy()
            portfolio = Portfolio(initial_capital=100000.0)

            # Build bars_by_instrument with UPPERCASE keys (as WFO runner does)
            bars_by_instrument = {}
            if spx_count > 25:
                bars_by_instrument["SPX"] = spx_bars[:50]
            if dxy_count > 10:
                bars_by_instrument["DXY"] = dxy_bars[:50]

            print(f"   bars_by_instrument keys: {list(bars_by_instrument.keys())}")
            print()

            # Pick a date that triggers rebalance
            test_date = spx_bars[49].date if spx_count > 49 else spx_bars[-1].date
            actions = strat3.on_bar(test_date, bars_by_instrument, portfolio, None)
            print(f"   on_bar({test_date!r}) with UPPERCASE keys:")
            print(f"   Actions returned: {len(actions)}")
            for a in actions:
                print(f"     {a}")
            print()
            if len(actions) == 0:
                print("   BUG CONFIRMED: 0 actions because all instruments skipped.")
            print()

        # ── Summary ──
        print(SEPARATOR)
        print("SUMMARY OF CASE-SENSITIVITY BUGS IN macro_regime.py")
        print(SEPARATOR)
        print()
        print("PRIMARY BUG (line 213):")
        print("  ASSET_REGIME_DIR has lowercase keys (spx, eurusd, gold, ...)")
        print("  but bars_by_instrument has UPPERCASE keys (SPX, EURUSD, GOLD, ...)")
        print("  -> ASSET_REGIME_DIR.get(instrument) ALWAYS returns None")
        print("  -> `if asset_dir is None: continue` skips every instrument")
        print("  -> 0 trades generated")
        print()
        print("SECONDARY BUGS (same root cause):")
        print("  Line 167: 'spx' in bars_by_instrument -> False (keys are 'SPX')")
        print("  Line 168: 'nas100' in bars_by_instrument -> False (keys are 'NAS100')")
        print("  Line 174: 'dxy' in bars_by_instrument -> False (keys are 'DXY')")
        print("  Line 221: instrument in RISK_OFF_ASSETS -> False (UPPERCASE vs lowercase)")
        print("  Line 223: instrument in RISK_ON_ASSETS -> False (UPPERCASE vs lowercase)")
        print()
        print("FIX OPTIONS:")
        print("  A) Normalize instrument to lowercase in on_bar() before all lookups:")
        print('     `inst_lower = instrument.lower()` then use inst_lower for all')
        print("     dict/set lookups. Also lowercase the VIX/DXY proxy strings.")
        print()
        print("  B) Uppercase all constant keys (ASSET_REGIME_DIR, RISK_ON_ASSETS,")
        print("     RISK_OFF_ASSETS, VIX proxy list, dxy_instrument default).")
        print()
        print("  Option A is safer (single normalize point, works regardless of")
        print("  what case the runner sends). Option B requires updating 5+ constants.")
        print()


if __name__ == "__main__":
    main()
