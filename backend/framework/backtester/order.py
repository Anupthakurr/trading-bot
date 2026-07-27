"""
Order, Trade, and Position data models for the backtesting engine.

Defines the core data structures used throughout the backtester:
orders (buy/sell instructions), positions (open holdings), and
trades (completed round-trip transactions).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(Enum):
    """Order direction."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order execution type."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class PositionStatus(Enum):
    """Position lifecycle status."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass
class Order:
    """
    A single buy or sell order.

    Attributes:
        side: BUY or SELL.
        order_type: MARKET, LIMIT, or STOP.
        quantity: Number of shares/units.
        price: Execution price (after slippage/fees applied by engine).
        raw_price: Original signal price before slippage.
        timestamp: Bar date/time when the order was placed.
        bar_index: Index of the bar in the data array.
        commission: Fee paid for this order.
        slippage: Price difference due to slippage simulation.
        reason: Human-readable reason (from strategy signal).
    """
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: int = 0
    price: float = 0.0
    raw_price: float = 0.0
    timestamp: str = ""
    bar_index: int = 0
    commission: float = 0.0
    slippage: float = 0.0
    reason: str = ""


@dataclass
class Position:
    """
    An open position (long).

    Tracks entry details and current stop-loss/take-profit levels.
    """
    entry_order: Order = field(default_factory=Order)
    quantity: int = 0
    entry_price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None
    highest_price_since_entry: float = 0.0
    status: PositionStatus = PositionStatus.OPEN

    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L at current price."""
        return self.quantity * (current_price - self.entry_price)

    def market_value(self, current_price: float) -> float:
        """Current market value of the position."""
        return self.quantity * current_price


@dataclass
class Trade:
    """
    A completed round-trip trade (entry + exit).

    Created when a position is closed.
    """
    entry_order: Order = field(default_factory=Order)
    exit_order: Order = field(default_factory=Order)
    quantity: int = 0
    entry_price: float = 0.0
    exit_price: float = 0.0
    pnl: float = 0.0
    return_pct: float = 0.0
    commission_total: float = 0.0
    entry_date: str = ""
    exit_date: str = ""
    holding_bars: int = 0
    exit_reason: str = ""

    @property
    def is_winner(self) -> bool:
        """Whether this trade was profitable."""
        return self.pnl > 0

    @property
    def is_loser(self) -> bool:
        """Whether this trade was a loss."""
        return self.pnl < 0

    def to_dict(self) -> dict:
        """Convert to dict for CSV/JSON export."""
        return {
            "entry_date": self.entry_date,
            "exit_date": self.exit_date,
            "quantity": self.quantity,
            "entry_price": round(self.entry_price, 4),
            "exit_price": round(self.exit_price, 4),
            "pnl": round(self.pnl, 2),
            "return_pct": round(self.return_pct, 4),
            "commission": round(self.commission_total, 2),
            "holding_bars": self.holding_bars,
            "exit_reason": self.exit_reason,
            "winner": self.is_winner,
        }
