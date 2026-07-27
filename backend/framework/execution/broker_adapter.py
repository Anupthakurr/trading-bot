from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BrokerAdapter(ABC):
    """
    Abstract base class for all live execution brokers.
    All broker integrations (Zerodha, Upstox, Alpaca, etc.) must implement these methods.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Authenticate and connect to the broker."""
        ...

    @abstractmethod
    def get_live_price(self, ticker: str) -> float:
        """Fetch the current market price for a ticker."""
        ...

    @abstractmethod
    def place_market_order(self, ticker: str, side: str, quantity: int) -> Dict[str, Any]:
        """
        Place a market order.
        Side must be 'BUY' or 'SELL'.
        Returns order details/confirmation from the broker.
        """
        ...

    @abstractmethod
    def place_limit_order(self, ticker: str, side: str, quantity: int, price: float) -> Dict[str, Any]:
        """
        Place a limit order.
        Side must be 'BUY' or 'SELL'.
        Returns order details/confirmation from the broker.
        """
        ...

    @abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Fetch all currently open positions from the broker."""
        ...

    @abstractmethod
    def get_account_balance(self) -> float:
        """Fetch the available cash balance from the broker."""
        ...
