"""
Portfolio management — account balance, equity tracking, and order execution.

The Portfolio is the central accounting unit of the backtester. It tracks:
- Cash balance
- Open positions
- Closed trades (complete round-trips)
- Equity curve (portfolio value at each bar)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from framework.backtester.order import (
    Order, OrderSide, OrderType, Position, PositionStatus, Trade,
)
from framework.backtester.execution import (
    apply_slippage, apply_commission, check_stop_loss, check_take_profit,
    update_trailing_stop, calculate_position_size,
)
from framework.config.settings import ExecutionConfig
from framework.strategies.base import Signal, StrategySignal

logger = logging.getLogger(__name__)


@dataclass
class Portfolio:
    """
    Manages account state throughout a backtest.

    Handles cash tracking, position management, order execution,
    and equity curve recording.
    """

    initial_capital: float = 100000.0
    cash: float = 100000.0
    execution_config: ExecutionConfig = field(default_factory=ExecutionConfig)
    risk_per_trade: float = 0.01

    # State
    position: Optional[Position] = None
    closed_trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    cash_curve: List[float] = field(default_factory=list)

    # For ATR trailing stop
    atr_multiplier: float = 2.0

    def reset(self) -> None:
        """Reset portfolio to initial state."""
        self.cash = self.initial_capital
        self.position = None
        self.closed_trades = []
        self.equity_curve = []
        self.cash_curve = []

    @property
    def has_position(self) -> bool:
        """Whether there is an open position."""
        return self.position is not None and self.position.status == PositionStatus.OPEN

    def equity(self, current_price: float) -> float:
        """Total portfolio value (cash + position market value)."""
        if self.has_position:
            return self.cash + self.position.market_value(current_price)
        return self.cash

    def update(self, bar_index: int, data: pd.DataFrame) -> Optional[str]:
        """
        Called each bar to mark-to-market and check SL/TP.

        Args:
            bar_index: Current bar index.
            data: Full OHLCV DataFrame with indicators.

        Returns:
            Exit reason if position was closed by SL/TP, None otherwise.
        """
        row = data.iloc[bar_index]
        current_price = row["Close"]
        exit_reason = None

        if self.has_position:
            # Check stop-loss (uses bar Low)
            sl_price = check_stop_loss(
                self.position,
                bar_low=row["Low"],
                bar_high=row["High"],
            )
            if sl_price is not None:
                exit_reason = "Stop-loss triggered"
                self._close_position(
                    exit_price=sl_price,
                    bar_index=bar_index,
                    timestamp=str(row.get("Date", bar_index)),
                    reason=exit_reason,
                )
            else:
                # Check take-profit (uses bar High)
                tp_price = check_take_profit(self.position, bar_high=row["High"])
                if tp_price is not None:
                    exit_reason = "Take-profit triggered"
                    self._close_position(
                        exit_price=tp_price,
                        bar_index=bar_index,
                        timestamp=str(row.get("Date", bar_index)),
                        reason=exit_reason,
                    )
                else:
                    # Update trailing stop if ATR available
                    atr_val = row.get("ATR", 0)
                    if not pd.isna(atr_val) and atr_val > 0:
                        update_trailing_stop(
                            self.position,
                            current_high=row["High"],
                            atr_value=atr_val,
                            atr_multiplier=self.atr_multiplier,
                        )

        # Record equity
        eq = self.equity(current_price)
        self.equity_curve.append(eq)
        self.cash_curve.append(self.cash)

        return exit_reason

    def execute_signal(
        self,
        signal: StrategySignal,
        bar_index: int,
        data: pd.DataFrame,
    ) -> None:
        """
        Execute a strategy signal (open or close a position).

        Args:
            signal: Strategy signal (BUY/SELL/HOLD).
            bar_index: Current bar index.
            data: Full DataFrame.
        """
        if signal.action == Signal.HOLD:
            return

        row = data.iloc[bar_index]
        timestamp = str(row.get("Date", bar_index))

        if signal.action == Signal.BUY and not self.has_position:
            self._open_position(signal, bar_index, timestamp, data)

        elif signal.action == Signal.SELL and self.has_position:
            self._close_position(
                exit_price=signal.price,
                bar_index=bar_index,
                timestamp=timestamp,
                reason=signal.reason,
            )

    def _open_position(
        self,
        signal: StrategySignal,
        bar_index: int,
        timestamp: str,
        data: pd.DataFrame,
    ) -> None:
        """Open a new long position."""
        # Apply slippage
        exec_price, slip = apply_slippage(
            signal.price, "BUY", self.execution_config
        )

        # Calculate position size
        quantity = calculate_position_size(
            capital=self.cash,
            price=exec_price,
            risk_per_trade=self.risk_per_trade,
            stop_loss=signal.stop_loss,
            max_position_pct=self.execution_config.max_position_pct,
        )

        if quantity <= 0:
            logger.debug("Skip BUY — insufficient capital or zero position size")
            return

        # Calculate commission
        trade_value = exec_price * quantity
        commission = apply_commission(trade_value, self.execution_config)

        # Check affordability
        total_cost = trade_value + commission
        if total_cost > self.cash:
            # Reduce quantity to fit
            quantity = int((self.cash - commission) / exec_price)
            if quantity <= 0:
                logger.debug("Skip BUY — cannot afford even 1 unit after fees")
                return
            trade_value = exec_price * quantity
            commission = apply_commission(trade_value, self.execution_config)

        # Create order
        order = Order(
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=quantity,
            price=exec_price,
            raw_price=signal.price,
            timestamp=timestamp,
            bar_index=bar_index,
            commission=commission,
            slippage=slip,
            reason=signal.reason,
        )

        # Create position
        self.position = Position(
            entry_order=order,
            quantity=quantity,
            entry_price=exec_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            trailing_stop=signal.stop_loss,  # Initial trailing = fixed SL
            highest_price_since_entry=exec_price,
            status=PositionStatus.OPEN,
        )

        # Deduct cash
        self.cash -= (trade_value + commission)

        logger.debug(
            "OPEN: %d units @ %.4f (SL=%.4f) | Cash: %.2f",
            quantity, exec_price,
            signal.stop_loss or 0, self.cash,
        )

    def _close_position(
        self,
        exit_price: float,
        bar_index: int,
        timestamp: str,
        reason: str,
    ) -> None:
        """Close an open position and record the trade."""
        if not self.has_position:
            return

        pos = self.position

        # Apply slippage on exit
        exec_price, slip = apply_slippage(
            exit_price, "SELL", self.execution_config
        )

        # Commission
        trade_value = exec_price * pos.quantity
        commission = apply_commission(trade_value, self.execution_config)

        # P&L
        gross_pnl = pos.quantity * (exec_price - pos.entry_price)
        total_commission = pos.entry_order.commission + commission
        net_pnl = gross_pnl - total_commission

        return_pct = (exec_price - pos.entry_price) / pos.entry_price if pos.entry_price > 0 else 0

        # Create exit order
        exit_order = Order(
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=pos.quantity,
            price=exec_price,
            raw_price=exit_price,
            timestamp=timestamp,
            bar_index=bar_index,
            commission=commission,
            slippage=slip,
            reason=reason,
        )

        # Record trade
        trade = Trade(
            entry_order=pos.entry_order,
            exit_order=exit_order,
            quantity=pos.quantity,
            entry_price=pos.entry_price,
            exit_price=exec_price,
            pnl=net_pnl,
            return_pct=return_pct,
            commission_total=total_commission,
            entry_date=pos.entry_order.timestamp,
            exit_date=timestamp,
            holding_bars=bar_index - pos.entry_order.bar_index,
            exit_reason=reason,
        )

        self.closed_trades.append(trade)

        # Return cash
        self.cash += trade_value - commission

        logger.debug(
            "CLOSE: %d units @ %.4f | PnL: %.2f (%.2f%%) | %s",
            pos.quantity, exec_price, net_pnl, return_pct * 100, reason,
        )

        # Clear position
        self.position = None

    def force_close(self, bar_index: int, data: pd.DataFrame) -> None:
        """Force-close any open position at end of backtest."""
        if self.has_position:
            row = data.iloc[bar_index]
            self._close_position(
                exit_price=row["Close"],
                bar_index=bar_index,
                timestamp=str(row.get("Date", bar_index)),
                reason="End of backtest (forced close)",
            )
