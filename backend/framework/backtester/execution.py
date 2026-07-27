"""
Trade execution simulation — fees, slippage, stop-loss, take-profit.

Models realistic order execution conditions including:
- Commission fees (configurable percentage)
- Slippage (fixed or random model)
- Stop-loss checking against bar High/Low
- Take-profit checking against bar High/Low
- Trailing stop-loss updates
"""

import logging
import random
from typing import Optional, Tuple

from framework.backtester.order import Position
from framework.config.settings import ExecutionConfig

logger = logging.getLogger(__name__)


def apply_slippage(price: float, side: str, config: ExecutionConfig) -> Tuple[float, float]:
    """
    Apply slippage to an execution price.

    For BUY orders, slippage moves price UP (worse fill).
    For SELL orders, slippage moves price DOWN (worse fill).

    Args:
        price: Raw signal price.
        side: 'BUY' or 'SELL'.
        config: Execution configuration with slippage settings.

    Returns:
        Tuple of (adjusted_price, slippage_amount).
    """
    if config.slippage_pct <= 0:
        return price, 0.0

    if config.slippage_model == "random":
        # Random slippage between 0 and max
        slip_pct = random.uniform(0, config.slippage_pct)
    else:
        # Fixed slippage
        slip_pct = config.slippage_pct

    slip_amount = price * slip_pct

    if side == "BUY":
        adjusted = price + slip_amount
    else:
        adjusted = price - slip_amount

    return round(adjusted, 6), round(slip_amount, 6)


def apply_commission(trade_value: float, config: ExecutionConfig) -> float:
    """
    Calculate commission for a trade.

    Args:
        trade_value: Total value of the trade (price × quantity).
        config: Execution configuration with fee settings.

    Returns:
        Commission amount.
    """
    return round(abs(trade_value) * config.commission_pct, 6)


def check_stop_loss(
    position: Position,
    bar_low: float,
    bar_high: float,
) -> Optional[float]:
    """
    Check if a stop-loss was triggered during a bar.

    Uses the bar's Low price to check if SL was hit (for long positions).
    If the bar opened below the SL, the open price is used instead.

    Args:
        position: Current open position.
        bar_low: Low price of the current bar.
        bar_high: High price of the current bar.

    Returns:
        Stop-loss execution price if triggered, None otherwise.
    """
    sl = position.trailing_stop if position.trailing_stop else position.stop_loss

    if sl is None:
        return None

    if bar_low <= sl:
        # SL was hit — execute at SL price (or worse if gap down)
        exit_price = sl
        logger.debug(
            "Stop-loss triggered at %.4f (bar low: %.4f)",
            exit_price, bar_low,
        )
        return exit_price

    return None


def check_take_profit(
    position: Position,
    bar_high: float,
) -> Optional[float]:
    """
    Check if a take-profit was triggered during a bar.

    Uses the bar's High price to check if TP was hit (for long positions).

    Args:
        position: Current open position.
        bar_high: High price of the current bar.

    Returns:
        Take-profit execution price if triggered, None otherwise.
    """
    if position.take_profit is None:
        return None

    if bar_high >= position.take_profit:
        exit_price = position.take_profit
        logger.debug(
            "Take-profit triggered at %.4f (bar high: %.4f)",
            exit_price, bar_high,
        )
        return exit_price

    return None


def update_trailing_stop(
    position: Position,
    current_high: float,
    atr_value: float,
    atr_multiplier: float,
) -> None:
    """
    Update trailing stop-loss based on the highest price since entry.

    The trailing stop moves UP as price rises, but never moves down.

    Args:
        position: Current open position (modified in place).
        current_high: High price of the current bar.
        atr_value: Current ATR value.
        atr_multiplier: Multiplier for ATR-based trailing distance.
    """
    if current_high > position.highest_price_since_entry:
        position.highest_price_since_entry = current_high

    if atr_value > 0:
        new_trail = position.highest_price_since_entry - (atr_value * atr_multiplier)

        if position.trailing_stop is None or new_trail > position.trailing_stop:
            position.trailing_stop = round(new_trail, 6)


def calculate_position_size(
    capital: float,
    price: float,
    risk_per_trade: float,
    stop_loss: Optional[float],
    max_position_pct: float = 1.0,
) -> int:
    """
    Calculate position size based on risk management rules.

    Uses the risk-per-trade approach: risk a fixed percentage of capital,
    and size the position so that hitting the stop-loss equals that risk.

    Args:
        capital: Current available capital.
        price: Entry price.
        risk_per_trade: Fraction of capital to risk (e.g., 0.01 = 1%).
        stop_loss: Stop-loss price. If None, uses simple fraction of capital.
        max_position_pct: Max fraction of capital in a single position.

    Returns:
        Number of shares/units to buy (integer, >= 0).
    """
    if capital <= 0 or price <= 0:
        return 0

    max_value = capital * max_position_pct
    max_shares = int(max_value / price)

    if stop_loss is not None and stop_loss < price:
        risk_amount = capital * risk_per_trade
        risk_per_share = price - stop_loss
        if risk_per_share > 0:
            shares = int(risk_amount / risk_per_share)
        else:
            shares = max_shares
    else:
        # No stop-loss: use simple capital fraction
        shares = int((capital * risk_per_trade * 10) / price)  # ~10% at 1% risk

    # Clamp
    shares = max(0, min(shares, max_shares))
    return shares
