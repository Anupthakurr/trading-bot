import logging
import uuid
import yfinance as yf
from typing import Dict, Any, List

from framework.execution.broker_adapter import BrokerAdapter

logger = logging.getLogger(__name__)

class MockBrokerAdapter(BrokerAdapter):
    """
    A mock broker for forward testing and paper trading without risking real money.
    Fetches actual prices from Yahoo Finance but keeps trades in memory.
    """

    def __init__(self, initial_balance: float = 100000.0):
        self.balance = initial_balance
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.is_connected = False

    def connect(self) -> bool:
        logger.info("Connecting to Mock Broker...")
        self.is_connected = True
        return True

    def get_live_price(self, ticker: str) -> float:
        if not self.is_connected:
            raise ConnectionError("Mock broker is not connected")
        
        try:
            # Fetch latest data from yfinance
            t = yf.Ticker(ticker)
            data = t.history(period="1d", interval="1m")
            if not data.empty:
                return float(data['Close'].iloc[-1])
            return 0.0
        except Exception as e:
            logger.error(f"Failed to fetch mock price for {ticker}: {e}")
            return 0.0

    def place_market_order(self, ticker: str, side: str, quantity: int) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Mock broker is not connected")
            
        current_price = self.get_live_price(ticker)
        trade_value = current_price * quantity
        
        if side == 'BUY':
            if self.balance < trade_value:
                logger.warning(f"Insufficient mock funds to buy {quantity} {ticker}")
                return {"status": "REJECTED", "reason": "Insufficient funds"}
            
            self.balance -= trade_value
            if ticker in self.positions:
                old_qty = self.positions[ticker]["quantity"]
                old_price = self.positions[ticker]["entry_price"]
                new_qty = old_qty + quantity
                new_price = ((old_qty * old_price) + (quantity * current_price)) / new_qty
                self.positions[ticker] = {"quantity": new_qty, "entry_price": new_price}
            else:
                self.positions[ticker] = {"quantity": quantity, "entry_price": current_price}
                
        elif side == 'SELL':
            if ticker not in self.positions or self.positions[ticker]["quantity"] < quantity:
                logger.warning(f"Insufficient mock position to sell {quantity} {ticker}")
                return {"status": "REJECTED", "reason": "Insufficient position"}
                
            self.balance += trade_value
            self.positions[ticker]["quantity"] -= quantity
            if self.positions[ticker]["quantity"] == 0:
                del self.positions[ticker]
                
        order_id = f"mock_{uuid.uuid4().hex[:8]}"
        logger.info(f"Mock Order Filled: {side} {quantity} {ticker} @ {current_price} [ID: {order_id}]")
        
        return {
            "order_id": order_id,
            "ticker": ticker,
            "side": side,
            "status": "FILLED",
            "quantity": quantity,
            "filled_price": current_price
        }

    def place_limit_order(self, ticker: str, side: str, quantity: int, price: float) -> Dict[str, Any]:
        # Limit orders are complex to mock perfectly without a constant tick stream.
        # For simplicity, we just reject or auto-fill them if they cross the spread instantly.
        return {"status": "REJECTED", "reason": "Limit orders not fully supported in MockBrokerAdapter yet"}

    def get_open_positions(self) -> List[Dict[str, Any]]:
        return [{"ticker": k, **v} for k, v in self.positions.items()]

    def get_account_balance(self) -> float:
        return self.balance
