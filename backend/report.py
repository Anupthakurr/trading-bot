#!/usr/bin/env python3
"""
CLI tool: Generate reports from saved backtest results.

Usage:
    python report.py --results results/AAPL_v3_1D
    python report.py --results results/AAPL_v3_1D --format html,csv,json
    python report.py --compare results/AAPL_v3_1D results/AAPL_v4_1D
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="QuantEngine — Report Generator",
    )
    parser.add_argument("--results", type=str, nargs="+", default=None,
                        help="Path(s) to results directory/directories")
    parser.add_argument("--format", type=str, default="html,csv,json",
                        help="Output formats, comma-separated")
    parser.add_argument("--compare", action="store_true",
                        help="Generate comparison table across multiple results")
    parser.add_argument("--list", action="store_true",
                        help="List available result directories")
    return parser.parse_args()


def list_results() -> None:
    """List all available result directories."""
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    if not os.path.exists(results_dir):
        print("  No results directory found. Run a backtest first.")
        return

    dirs = [d for d in os.listdir(results_dir)
            if os.path.isdir(os.path.join(results_dir, d))]

    if not dirs:
        print("  No result directories found.")
        return

    print(f"\n  Available results ({len(dirs)}):")
    for d in sorted(dirs):
        summary_path = os.path.join(results_dir, d, "summary.json")
        if os.path.exists(summary_path):
            try:
                with open(summary_path, "r") as f:
                    data = json.load(f)
                metrics = data.get("metrics", {})
                print(
                    f"    {d:<40} "
                    f"Return: {metrics.get('total_return_pct', 0):>8.2f}%  "
                    f"Sharpe: {metrics.get('sharpe_ratio', 0):>6.2f}  "
                    f"Trades: {metrics.get('num_trades', 0):>4d}"
                )
            except Exception:
                print(f"    {d}")
        else:
            print(f"    {d} (no summary.json)")
    print()


def compare_results(result_dirs: list) -> None:
    """Generate a comparison table across multiple result directories."""
    print(f"\n{'='*90}")
    print(f"  COMPARISON TABLE")
    print(f"{'='*90}")
    print(f"{'Name':<30} {'Return%':>9} {'Sharpe':>8} {'MaxDD%':>8} {'WinR%':>7} {'PF':>7} {'Trades':>7}")
    print(f"{'-'*90}")

    for rdir in result_dirs:
        summary_path = os.path.join(rdir, "summary.json")
        if not os.path.exists(summary_path):
            summary_path = os.path.join(
                os.path.dirname(__file__), "results", rdir, "summary.json"
            )

        if not os.path.exists(summary_path):
            print(f"  {rdir:<28} - summary.json not found")
            continue

        try:
            with open(summary_path, "r") as f:
                data = json.load(f)
            m = data.get("metrics", {})
            name = os.path.basename(os.path.dirname(summary_path) if summary_path.endswith("summary.json") else rdir)
            if not name or name == "summary.json":
                name = rdir

            print(
                f"  {name:<28} "
                f"{m.get('total_return_pct', 0):>8.2f}% "
                f"{m.get('sharpe_ratio', 0):>8.2f} "
                f"{m.get('max_drawdown_pct', 0):>7.2f}% "
                f"{m.get('win_rate_pct', 0):>6.1f}% "
                f"{m.get('profit_factor', 0):>7.2f} "
                f"{m.get('num_trades', 0):>6d}"
            )
        except Exception as e:
            print(f"  {rdir:<28} - Error: {e}")

    print(f"{'='*90}\n")


def main() -> None:
    args = parse_args()

    print(f"\n{'='*60}")
    print(f"  QuantEngine Report Generator")
    print(f"{'='*60}")

    if args.list:
        list_results()
        return

    if args.results is None:
        print("\n  No results specified. Use --results or --list.")
        print("  Example: python report.py --list")
        print("  Example: python report.py --results results/AAPL_v3_1D\n")
        return

    if args.compare or len(args.results) > 1:
        compare_results(args.results)
    else:
        result_dir = args.results[0]
        if not os.path.isabs(result_dir):
            result_dir = os.path.join(os.path.dirname(__file__), result_dir)

        summary_path = os.path.join(result_dir, "summary.json")
        if os.path.exists(summary_path):
            with open(summary_path, "r") as f:
                data = json.load(f)

            print(f"\n  Result: {os.path.basename(result_dir)}")
            print(f"  Strategy: {data.get('backtest', {}).get('strategy', '?')}")
            print(f"  Symbol: {data.get('backtest', {}).get('symbol', '?')}")
            print()

            m = data.get("metrics", {})
            for key, val in m.items():
                print(f"    {key:<25}: {val}")
            print()

            # List available files
            files = os.listdir(result_dir)
            print(f"  Available files:")
            for f_name in sorted(files):
                size = os.path.getsize(os.path.join(result_dir, f_name))
                print(f"    {f_name:<40} ({size:>8,d} bytes)")
            print()
        else:
            print(f"\n  [ERROR] No summary.json found in {result_dir}")
            print(f"     Run a backtest first: python backtest.py --symbol AAPL\n")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
