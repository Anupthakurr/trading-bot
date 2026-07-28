import pandas as pd
import numpy as np

def calculate_rsi(data: pd.Series, periods: int = 14) -> pd.Series:
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df: pd.DataFrame, periods: int = 14) -> pd.Series:
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(periods).mean()

def run_backtest(
    df: pd.DataFrame, 
    strategy_version: int = 1,
    short_window: int = 20, 
    long_window: int = 50,
    rsi_period: int = 14,
    atr_multiplier: float = 2.0,
    risk_per_trade: float = 0.01, # 1% risk
    initial_capital: float = 100000.0
) -> dict:
    
    data = df.copy()
    
    # Calculate indicators
    data['SMA_short'] = data['Close'].rolling(window=short_window, min_periods=1).mean()
    data['SMA_long'] = data['Close'].rolling(window=long_window, min_periods=1).mean()
    data['RSI'] = calculate_rsi(data['Close'], periods=rsi_period)
    data['ATR'] = calculate_atr(data, periods=14)
    
    # Default columns
    data['Signal'] = 0.0
    data['Position'] = 0.0
    data['Equity'] = initial_capital
    data['Asset_Return'] = data['Close'].pct_change()
    data['Buy_and_Hold_Equity'] = initial_capital * (1 + data['Asset_Return'].fillna(0)).cumprod()
    
    if strategy_version == 1 or strategy_version == 2:
        # Vectorized implementation for V1 and V2
        if strategy_version == 1:
            data['Signal'] = np.where(data['SMA_short'] > data['SMA_long'], 1.0, 0.0)
        elif strategy_version == 2:
            # Buy if crossover AND not overbought
            # Sell if crossunder OR overbought
            buy_condition = (data['SMA_short'] > data['SMA_long']) & (data['RSI'] < 70)
            data['Signal'] = np.where(buy_condition, 1.0, 0.0)
            
        data['Position'] = data['Signal'].diff()
        data['Strategy_Return'] = data['Signal'].shift(1) * data['Asset_Return']
        data['Equity'] = initial_capital * (1 + data['Strategy_Return'].fillna(0)).cumprod()

    elif strategy_version == 3:
        # Path-dependent implementation (loop) for V3 (ATR Stop Loss & Position Sizing)
        equity = initial_capital
        position = 0 # shares held
        entry_price = 0
        stop_loss_price = 0
        
        equity_curve = []
        signals = []
        positions = []
        
        for i in range(len(data)):
            if i == 0:
                equity_curve.append(equity)
                signals.append(0)
                positions.append(0)
                continue
                
            today = data.iloc[i]
            yesterday = data.iloc[i-1]
            
            # Update equity mark-to-market
            current_capital = equity
            if position > 0:
                current_capital = equity + position * (today['Close'] - entry_price)
                
            # Check Stop Loss
            if position > 0 and today['Close'] <= stop_loss_price:
                # Sell (Stop Loss Hit)
                equity = current_capital
                position = 0
                signals.append(-1.0)
                positions.append(0)
                equity_curve.append(equity)
                continue
                
            # Check Exit Signal (SMA Cross under OR RSI overbought)
            if position > 0 and (today['SMA_short'] < today['SMA_long'] or today['RSI'] > 70):
                equity = current_capital
                position = 0
                signals.append(-1.0)
                positions.append(0)
                equity_curve.append(equity)
                continue
                
            # Check Entry Signal
            if position == 0 and today['SMA_short'] > today['SMA_long'] and today['RSI'] < 70:
                # Calculate Position Size based on ATR Risk
                risk_amount = current_capital * risk_per_trade
                atr_risk = today['ATR'] * atr_multiplier
                if atr_risk > 0:
                    shares_to_buy = int(risk_amount / atr_risk)
                    max_shares = int(current_capital / today['Close'])
                    shares_to_buy = min(shares_to_buy, max_shares) # Cannot buy more than we can afford
                    
                    if shares_to_buy > 0:
                        position = shares_to_buy
                        entry_price = today['Close']
                        stop_loss_price = entry_price - atr_risk
                        signals.append(1.0)
                        positions.append(position)
                        equity_curve.append(current_capital)
                        continue
                        
            # Hold
            signals.append(0.0)
            positions.append(position)
            equity_curve.append(current_capital)
            
        data['Equity'] = equity_curve
        data['Signal'] = signals
        data['Position'] = positions

    # Metrics calculation (same for all)
    total_return = (data['Equity'].iloc[-1] / initial_capital) - 1
    buy_hold_return = (data['Buy_and_Hold_Equity'].iloc[-1] / initial_capital) - 1
    
    # Daily returns of the strategy equity
    strat_daily_returns = data['Equity'].pct_change().fillna(0)
    market_returns = data['Asset_Return'].fillna(0)
    
    risk_free_rate = 0.02
    daily_rf = risk_free_rate / 252
    excess_returns = strat_daily_returns - daily_rf
    
    if excess_returns.std() > 0:
        sharpe_ratio = np.sqrt(252) * (excess_returns.mean() / excess_returns.std())
    else:
        sharpe_ratio = 0.0
        
    downside_returns = excess_returns[excess_returns < 0]
    downside_std = downside_returns.std()
    if pd.isna(downside_std) or downside_std == 0:
        sortino_ratio = 0.0
    else:
        sortino_ratio = np.sqrt(252) * (excess_returns.mean() / downside_std)
        
    cumulative_max = data['Equity'].cummax()
    drawdown = (data['Equity'] - cumulative_max) / cumulative_max
    max_drawdown = drawdown.min()
    data['Drawdown'] = drawdown * 100
    
    years = len(data) / 252
    annualized_return = ((data['Equity'].iloc[-1] / initial_capital) ** (1 / years)) - 1 if years > 0 and (data['Equity'].iloc[-1] / initial_capital) > 0 else 0
    market_annualized = ((data['Buy_and_Hold_Equity'].iloc[-1] / initial_capital) ** (1 / years)) - 1 if years > 0 and (data['Buy_and_Hold_Equity'].iloc[-1] / initial_capital) > 0 else 0
    
    calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown < 0 else 0
    
    var_market = np.var(market_returns)
    beta = np.cov(strat_daily_returns, market_returns)[0][1] / var_market if var_market > 0 else 1.0
    alpha = annualized_return - (risk_free_rate + beta * (market_annualized - risk_free_rate))
    
    winning_days = len(strat_daily_returns[strat_daily_returns > 0])
    losing_days = len(strat_daily_returns[strat_daily_returns < 0])
    win_rate = winning_days / (winning_days + losing_days) if (winning_days + losing_days) > 0 else 0
    
    # Fill NaN for JSON serialization
    data.fillna(0, inplace=True)
    
    chart_data = data[['Date', 'Close', 'SMA_short', 'SMA_long', 'Signal', 'Position', 'Equity', 'Drawdown']].to_dict(orient='records')
    
    return {
        "metrics": {
            "initial_capital": initial_capital,
            "final_equity": round(data['Equity'].iloc[-1], 2),
            "total_return_pct": round(total_return * 100, 2),
            "buy_and_hold_return_pct": round(buy_hold_return * 100, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "calmar_ratio": round(calmar_ratio, 2),
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "alpha_pct": round(alpha * 100, 2),
            "beta": round(beta, 2),
            "win_rate_pct": round(win_rate * 100, 2),
            "winning_trades": winning_days,
            "losing_trades": losing_days
        },
        "chart_data": chart_data
    }
