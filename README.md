# QuantEngine Trading Bot

A professional, robust backtesting and optimization framework built for quantitative trading strategies.

## 🚀 Features

- **Zero Look-Ahead Bias**: Replays historical data bar-by-bar, strictly separating indicator calculation from signal generation.
- **Realistic Execution**: Simulates percentage-based commission fees, slippage (fixed or random), and exact stop-loss/take-profit triggers.
- **Comprehensive Analytics**: Computes 13+ professional metrics including Sharpe Ratio, Sortino Ratio, Calmar Ratio, Maximum Drawdown, Expectancy, and Profit Factor.
- **Advanced Optimization**: Features exhaustive Grid Search, Random Search for large parameter spaces, and Walk-Forward Analysis to detect overfitting.
- **Robustness Testing**: Includes Monte Carlo simulations (trade order shuffling) and Parameter Sensitivity Analysis to ensure strategies are statistically sound.
- **Beautiful Visualization**: Generates 6 different chart types (Equity Curve, Drawdown, Trade Distribution, Monthly Returns Heatmap, Price Signals, and a full Dashboard).
- **Flexible Reporting**: Exports results as interactive HTML reports, JSON summaries, and CSV trade logs.

## 📁 Directory Structure

```
trading bot/
├── backend/
│   ├── framework/
│   │   ├── backtester/     # Core bar-by-bar engine and portfolio management
│   │   ├── config/         # Strongly-typed configuration system
│   │   ├── data/           # Historical data provider (yfinance) and caching
│   │   ├── metrics/        # Performance metric calculator
│   │   ├── optimization/   # Grid Search, Random Search, Walk-Forward Analysis
│   │   ├── reporting/      # HTML, JSON, and CSV report generators
│   │   ├── robustness/     # Monte Carlo and Sensitivity analysis
│   │   ├── strategies/     # Strategy interface and implementations (V1-V4)
│   │   └── visualization/  # Matplotlib chart generators
│   ├── backtest.py         # CLI tool for running backtests
│   ├── optimize.py         # CLI tool for running optimizations
│   ├── report.py           # CLI tool for viewing and comparing reports
│   ├── config.yaml         # Master configuration file
│   └── requirements.txt    # Python dependencies
├── frontend/               # React-based User Interface
└── ...
```

## 🛠️ Installation

1. Navigate to the `backend` directory.
2. Create and activate a virtual environment.
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## 💻 CLI Usage

All CLI tools are located in the `backend/` directory.

### Run a Backtest
```bash
python backtest.py --symbol AAPL --timeframe 1D --strategy v4 --start 2023-01-01 --end 2024-01-01
```

### Run an Optimization
```bash
# Exhaustive grid search
python optimize.py --symbol MSFT --strategy v4 --method grid

# Walk-forward analysis
python optimize.py --symbol SPY --strategy v3 --method walk-forward
```

### View & Compare Reports
```bash
# List all previous backtest runs
python report.py --list

# View a summary of a specific run
python report.py --results results/AAPL_v4_1D
```

## 📈 Included Strategies

- **V1 (SMA Crossover)**: A simple moving average crossover strategy.
- **V2 (SMA + RSI)**: Moving average crossover with an RSI filter.
- **V3 (ATR Risk Management)**: Adds ATR-based position sizing and trailing stops.
- **V4 (Enhanced Momentum)**: A professional momentum strategy utilizing Fast/Slow EMAs, MACD confirmation, RSI thresholding, and dynamic ATR trailing stops.

## 📝 License

Proprietary - All rights reserved.
