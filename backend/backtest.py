#!/usr/bin/env python3
"""
CLI tool: Run a backtest.

Usage:
    python backtest.py --symbol AAPL --timeframe 1D --strategy v3
    python backtest.py --symbol BTCUSDT,ETHUSDT --timeframe 1h --strategy v4
    python backtest.py --symbol SPY --strategy v1 --start 2023-01-01 --end 2024-12-31
    python backtest.py --config config.yaml

All results (charts, reports, CSVs) are saved to the results/ directory.
"""

import argparse
import logging
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from framework.config.settings import load_settings
from framework.data.provider import YFinanceProvider
from framework.data.cache import DataCache
from framework.data.timeframes import Timeframe
from framework.strategies.adapter import get_strategy
from framework.backtester.engine import BacktestEngine
from framework.metrics.calculator import MetricsCalculator
from framework.visualization.charts import generate_all_charts
from framework.reporting.html_report import generate_html_report
from framework.reporting.csv_export import export_trades_csv, export_equity_csv
from framework.reporting.json_export import export_json_summary
from framework.robustness.monte_carlo import monte_carlo_simulation

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="QuantEngine — Run a backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--symbol", "-s", type=str, default=None,
                        help="Asset symbol(s), comma-separated (e.g. AAPL,MSFT,SPY)")
    parser.add_argument("--timeframe", "-tf", type=str, default=None,
                        help="Timeframe: 5m, 15m, 1h, 4h, 1D")
    parser.add_argument("--strategy", "-st", type=str, default="v3",
                        help="Strategy version: v1, v2, v3, v4")
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--capital", type=float, default=None, help="Initial capital")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--monte-carlo", action="store_true", help="Run Monte Carlo simulation")
    parser.add_argument("--no-charts", action="store_true", help="Skip chart generation")
    parser.add_argument("--no-report", action="store_true", help="Skip HTML report")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load settings
    cli_overrides = {}
    if args.capital:
        cli_overrides["general"] = {"initial_capital": args.capital}

    settings = load_settings(config_path=args.config, cli_overrides=cli_overrides)

    # Resolve parameters
    symbols = (args.symbol or ",".join(settings.data.default_symbols)).split(",")
    symbols = [s.strip() for s in symbols if s.strip()]
    timeframe_str = args.timeframe or settings.data.default_timeframe
    timeframe = Timeframe.from_string(timeframe_str)
    start = args.start or settings.data.default_start
    end = args.end or settings.data.default_end
    strategy_version = args.strategy.lower().strip()

    # Strategy params from config
    strat_params = settings.strategies.get(strategy_version, {})

    print(f"\n{'='*60}")
    print(f"  QuantEngine Backtest")
    print(f"  Symbols   : {', '.join(symbols)}")
    print(f"  Timeframe : {timeframe.display_name}")
    print(f"  Strategy  : {strategy_version}")
    print(f"  Period    : {start} -> {end}")
    print(f"  Capital   : ${settings.initial_capital:,.2f}")
    print(f"{'='*60}\n")

    # Data provider
    cache = DataCache(
        cache_dir=settings.data_cache_dir,
        ttl_hours=settings.data.cache_ttl_hours,
    )
    provider = YFinanceProvider(cache=cache)

    # Backtest engine
    engine = BacktestEngine(settings)
    calc = MetricsCalculator(annualization_factor=timeframe.annualization_factor)

    # Output directory
    output_base = os.path.join(os.path.dirname(__file__), settings.output_dir)
    os.makedirs(output_base, exist_ok=True)

    # Run for each symbol
    for symbol in symbols:
        print(f"\n{'-'*50}")
        print(f"  Processing: {symbol}")
        print(f"{'-'*50}")

        try:
            # 1. Fetch data
            data = provider.fetch(symbol, timeframe, start, end)
            print(f"  Data: {len(data)} bars loaded")

            # 2. Create strategy
            strategy = get_strategy(strategy_version, params=strat_params)

            # 3. Run backtest
            result = engine.run(strategy, data, symbol=symbol, timeframe=timeframe_str)

            # 4. Calculate metrics
            metrics = calc.calculate(result)
            print(metrics.summary_table())

            # 5. Output directory for this symbol
            out_dir = os.path.join(output_base, f"{symbol}_{strategy_version}_{timeframe_str}")
            os.makedirs(out_dir, exist_ok=True)

            # 6. Generate charts
            charts = {}
            if not args.no_charts:
                charts = generate_all_charts(result, metrics, out_dir, dpi=settings.reporting.chart_dpi)
                print(f"  [Charts] Charts saved to {out_dir}")

            # 7. Generate reports
            if not args.no_report:
                html_path = os.path.join(out_dir, "report.html")
                generate_html_report(result, metrics, charts, html_path)
                print(f"  [Report] HTML report: {html_path}")

            # 8. CSV export
            csv_path = os.path.join(out_dir, "trades.csv")
            export_trades_csv(result.trades, csv_path)
            equity_csv = os.path.join(out_dir, "equity.csv")
            export_equity_csv(result, equity_csv)

            # 9. JSON export
            json_path = os.path.join(out_dir, "summary.json")
            export_json_summary(result, metrics, json_path)

            # 10. Monte Carlo (optional)
            if args.monte_carlo and result.trades:
                print("\n  Running Monte Carlo simulation...")
                mc = monte_carlo_simulation(
                    result.trades,
                    initial_capital=settings.initial_capital,
                    n_simulations=settings.robustness.monte_carlo_iterations,
                )
                print(mc.summary_table())

            print(f"\n  [SUCCESS] All outputs saved to: {out_dir}")

        except Exception as e:
            logger.error("Failed for %s: %s", symbol, e, exc_info=True)
            print(f"  [ERROR]: {e}")

    print(f"\n{'='*60}")
    print(f"  Backtest complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
