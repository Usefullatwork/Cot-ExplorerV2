"""
Report generator for backtesting results.
Produces text summaries, CSV trade logs, and equity curve data.
"""

import os
from typing import Dict

from . import metrics as m


def text_report(results: Dict) -> str:
    """Generate a formatted text performance report.

    Args:
        results: Output dict from BacktestEngine.report().

    Returns:
        Multi-line string with formatted report.
    """
    lines = []
    sep = "=" * 70

    lines.append(sep)
    lines.append(f"  BACKTEST REPORT: {results.get('strategy', 'Unknown')}")
    lines.append(sep)
    lines.append("")

    # Period
    period = results.get("period", {})
    lines.append(f"  Period:       {period.get('start', '?')} to {period.get('end', '?')}")
    lines.append(f"  Bars:         {period.get('bars', 0)}")
    lines.append(f"  Instruments:  {', '.join(results.get('instruments', []))}")
    lines.append("")

    # Capital
    cap = results.get("capital", {})
    lines.append("-" * 70)
    lines.append("  CAPITAL")
    lines.append("-" * 70)
    lines.append(f"  Initial:       ${cap.get('initial', 0):,.2f}")
    lines.append(f"  Final:         ${cap.get('final', 0):,.2f}")
    lines.append(f"  Total Return:  {cap.get('total_return_pct', 0):+.2f}%")
    net = cap.get("final", 0) - cap.get("initial", 0)
    lines.append(f"  Net P&L:       ${net:,.2f}")
    lines.append("")

    # Trade Statistics
    trades = results.get("trades", {})
    lines.append("-" * 70)
    lines.append("  TRADE STATISTICS")
    lines.append("-" * 70)
    lines.append(f"  Total Trades:  {trades.get('total', 0)}")
    lines.append(f"  Winners:       {trades.get('winners', 0)}")
    lines.append(f"  Losers:        {trades.get('losers', 0)}")
    lines.append(f"  Win Rate:      {trades.get('win_rate', 0):.1f}%")
    lines.append(f"  Avg P&L:       {trades.get('avg_pnl', 0):+.4f}")
    lines.append(f"  Avg Winner:    {trades.get('avg_winner', 0):+.4f}")
    lines.append(f"  Avg Loser:     {trades.get('avg_loser', 0):+.4f}")
    lines.append(f"  Profit Factor: {trades.get('profit_factor', 0):.2f}")
    lines.append(f"  Expectancy:    {trades.get('expectancy', 0):+.4f}")
    lines.append(f"  Avg Hold (bars): {trades.get('avg_bars_held', 0):.1f}")
    lines.append("")

    # Risk Metrics
    risk = results.get("risk", {})
    lines.append("-" * 70)
    lines.append("  RISK METRICS")
    lines.append("-" * 70)
    lines.append(f"  Sharpe Ratio:    {risk.get('sharpe_ratio', 0):.3f}")
    lines.append(f"  Sortino Ratio:   {risk.get('sortino_ratio', 0):.3f}")
    lines.append(f"  Max Drawdown:    {risk.get('max_drawdown_pct', 0):.2f}%")
    lines.append(f"  Calmar Ratio:    {risk.get('calmar_ratio', 0):.3f}")
    lines.append(f"  Recovery Factor: {risk.get('recovery_factor', 0):.2f}")
    lines.append("")

    # Trade log summary (last 10 trades)
    trade_log = results.get("trade_log", [])
    if trade_log:
        lines.append("-" * 70)
        lines.append("  RECENT TRADES (last 10)")
        lines.append("-" * 70)
        lines.append(f"  {'Date':<12} {'Inst':<10} {'Dir':<6} {'Entry':>10} {'Exit':>10} {'P&L':>10} {'Reason'}")
        lines.append(f"  {'-' * 12} {'-' * 10} {'-' * 6} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 15}")
        for t in trade_log[-10:]:
            entry = f"{t['entry_price']:.4f}" if t["entry_price"] < 100 else f"{t['entry_price']:.2f}"
            exit_p = (
                f"{t['exit_price']:.4f}"
                if t.get("exit_price") and t["exit_price"] < 100
                else (f"{t['exit_price']:.2f}" if t.get("exit_price") else "open")
            )
            pnl_str = f"{t['pnl']:+.4f}"
            lines.append(
                f"  {t['entry_date']:<12} {t['instrument']:<10} {t['direction']:<6} "
                f"{entry:>10} {exit_p:>10} {pnl_str:>10} {t.get('exit_reason', '')}"
            )
        lines.append("")

    # Monthly returns
    equity_curve = results.get("equity_curve", [])
    if equity_curve and len(equity_curve) > 4:
        monthly = m.monthly_returns(equity_curve)
        if monthly:
            lines.append("-" * 70)
            lines.append("  MONTHLY RETURNS")
            lines.append("-" * 70)
            for month_str, ret in monthly[-12:]:
                bar_len = int(abs(ret) * 2)
                bar_char = "+" if ret >= 0 else "-"
                bar = bar_char * min(bar_len, 40)
                lines.append(f"  {month_str}  {ret:+6.2f}%  {bar}")
            lines.append("")

    lines.append(sep)
    return "\n".join(lines)


def trade_log_csv(results: Dict) -> str:
    """Generate CSV trade log.

    Args:
        results: Output dict from BacktestEngine.report().

    Returns:
        CSV string with header and one row per trade.
    """
    header = [
        "id",
        "instrument",
        "direction",
        "entry_date",
        "entry_price",
        "exit_date",
        "exit_price",
        "stop_loss",
        "take_profit",
        "size",
        "pnl",
        "pnl_pct",
        "bars_held",
        "reason",
        "exit_reason",
    ]
    lines = [",".join(header)]

    for t in results.get("trade_log", []):
        row = [
            str(t.get("id", "")),
            t.get("instrument", ""),
            t.get("direction", ""),
            t.get("entry_date", ""),
            str(t.get("entry_price", "")),
            str(t.get("exit_date", "")),
            str(t.get("exit_price", "")),
            str(t.get("stop_loss", "")),
            str(t.get("take_profit", "")),
            str(t.get("size", "")),
            str(t.get("pnl", "")),
            str(t.get("pnl_pct", "")),
            str(t.get("bars_held", "")),
            _csv_escape(t.get("reason", "")),
            _csv_escape(t.get("exit_reason", "")),
        ]
        lines.append(",".join(row))

    return "\n".join(lines)


def equity_curve_csv(results: Dict) -> str:
    """Generate CSV of equity curve data.

    Args:
        results: Output dict from BacktestEngine.report().

    Returns:
        CSV string with date and equity columns.
    """
    lines = ["date,equity"]
    for date_str, equity in results.get("equity_curve", []):
        lines.append(f"{date_str},{equity:.2f}")
    return "\n".join(lines)


def save_report(results: Dict, output_dir: str, prefix: str = "backtest") -> Dict[str, str]:
    """Save all report files to disk.

    Args:
        results: Output dict from BacktestEngine.report().
        output_dir: Directory to write reports to.
        prefix: Filename prefix.

    Creates:
        {prefix}_report.txt
        {prefix}_trades.csv
        {prefix}_equity.csv
        {prefix}_results.json
    """
    import json

    os.makedirs(output_dir, exist_ok=True)

    # Text report
    txt_path = os.path.join(output_dir, f"{prefix}_report.txt")
    with open(txt_path, "w") as f:
        f.write(text_report(results))

    # Trade log CSV
    csv_path = os.path.join(output_dir, f"{prefix}_trades.csv")
    with open(csv_path, "w") as f:
        f.write(trade_log_csv(results))

    # Equity curve CSV
    eq_path = os.path.join(output_dir, f"{prefix}_equity.csv")
    with open(eq_path, "w") as f:
        f.write(equity_curve_csv(results))

    # Full JSON results (without equity curve for size)
    json_results = dict(results)
    json_results.pop("equity_curve", None)
    json_path = os.path.join(output_dir, f"{prefix}_results.json")
    with open(json_path, "w") as f:
        json.dump(json_results, f, indent=2, default=str)

    return {
        "report": txt_path,
        "trades": csv_path,
        "equity": eq_path,
        "json": json_path,
    }


def _csv_escape(value: str) -> str:
    """Escape a string for CSV (wrap in quotes if contains comma or quote)."""
    if not value:
        return ""
    if "," in value or '"' in value or "\n" in value:
        return '"' + value.replace('"', '""') + '"'
    return value
