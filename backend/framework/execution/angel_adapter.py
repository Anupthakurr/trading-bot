import os
import json
import urllib.request
import logging
from typing import Dict, Any, List, Optional
import pyotp
from SmartApi import SmartConnect

from framework.execution.broker_adapter import BrokerAdapter

logger = logging.getLogger(__name__)

class AngelOneBrokerAdapter(BrokerAdapter):
    """
    BrokerAdapter implementation for Angel One SmartAPI.
    """

    INSTRUMENT_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

    def __init__(self, api_key: str, client_code: str, password: str, totp_secret: str):
        self.api_key = api_key
        self.client_code = client_code
        self.password = password
        self.totp_secret = totp_secret
        
        self.api = SmartConnect(api_key=self.api_key)
        self.is_connected = False
        self.token_map: Dict[str, Dict[str, str]] = {}
        
    def connect(self) -> bool:
        logger.info("Connecting to Angel One SmartAPI...")
        try:
            totp = pyotp.TOTP(self.totp_secret).now()
            data = self.api.generateSession(self.client_code, self.password, totp)
            
            if data['status'] == False:
                logger.error(f"Angel One Login Failed: {data['message']}")
                return False
                
            # SmartConnect handles token state internally after generateSession
            logger.info("Successfully authenticated with Angel One.")
            self.is_connected = True
            
            # Download and parse instrument master
            self._load_instruments()
            
            return True
        except Exception as e:
            logger.error(f"Exception during Angel One connect: {e}")
            return False

    def _load_instruments(self):
        """Downloads the instrument master JSON and maps TICKER -> {symboltoken, tradingsymbol, exchange}"""
        logger.info("Downloading Angel One instrument master...")
        try:
            with urllib.request.urlopen(self.INSTRUMENT_URL) as url:
                data = json.loads(url.read().decode())
                
            # Filter for NSE EQ (Equity Cash) for now
            # Format: {'token': '3045', 'symbol': 'SBIN-EQ', 'name': 'SBIN', 'exch_seg': 'NSE'}
            for item in data:
                if item['exch_seg'] == 'NSE' and item['symbol'].endswith('-EQ'):
                    # Map standard ticker "SBIN" to the dictionary
                    ticker = item['name'].upper()
                    self.token_map[ticker] = {
                        'symboltoken': item['token'],
                        'tradingsymbol': item['symbol'],
                        'exchange': item['exch_seg']
                    }
            logger.info(f"Loaded {len(self.token_map)} NSE equity instruments.")
        except Exception as e:
            logger.error(f"Failed to load instrument master: {e}")

    def _resolve_symbol(self, ticker: str) -> Optional[Dict[str, str]]:
        """Returns the AngelOne token info for a standard ticker (e.g. SBIN)."""
        ticker = ticker.upper()
        if ticker in self.token_map:
            return self.token_map[ticker]
        logger.warning(f"Ticker {ticker} not found in Angel One instrument master.")
        return None

    def get_live_price(self, ticker: str) -> float:
        if not self.is_connected:
            raise ConnectionError("Not connected to Angel One")
            
        symbol_info = self._resolve_symbol(ticker)
        if not symbol_info:
            return 0.0
            
        try:
            response = self.api.ltpData(
                symbol_info['exchange'], 
                symbol_info['tradingsymbol'], 
                symbol_info['symboltoken']
            )
            if response['status']:
                return float(response['data']['ltp'])
            else:
                logger.error(f"Failed to fetch LTP for {ticker}: {response['message']}")
                return 0.0
        except Exception as e:
            logger.error(f"Exception fetching LTP for {ticker}: {e}")
            return 0.0

    def place_market_order(self, ticker: str, side: str, quantity: int) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Angel One")
            
        symbol_info = self._resolve_symbol(ticker)
        if not symbol_info:
            return {"status": "REJECTED", "reason": "Unknown ticker"}
            
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol_info['tradingsymbol'],
            "symboltoken": symbol_info['symboltoken'],
            "transactiontype": side.upper(), # BUY or SELL
            "exchange": symbol_info['exchange'],
            "ordertype": "MARKET",
            "producttype": "INTRADAY", # Use MIS for bot trading
            "duration": "DAY",
            "quantity": str(quantity)
        }
        
        try:
            order_id = self.api.placeOrder(orderparams)
            logger.info(f"Angel One Order Placed: {side} {quantity} {ticker} [ID: {order_id}]")
            # For market orders, we assume FILLED, but in reality we'd need to poll the orderbook
            return {
                "order_id": order_id,
                "ticker": ticker,
                "side": side,
                "status": "FILLED",
                "quantity": quantity,
                # SmartAPI placeOrder doesn't return fill price, so we fetch LTP
                "filled_price": self.get_live_price(ticker)
            }
        except Exception as e:
            logger.error(f"Failed to place market order for {ticker}: {e}")
            return {"status": "REJECTED", "reason": str(e)}

    def place_limit_order(self, ticker: str, side: str, quantity: int, price: float) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Angel One")
            
        symbol_info = self._resolve_symbol(ticker)
        if not symbol_info:
            return {"status": "REJECTED", "reason": "Unknown ticker"}
            
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol_info['tradingsymbol'],
            "symboltoken": symbol_info['symboltoken'],
            "transactiontype": side.upper(),
            "exchange": symbol_info['exchange'],
            "ordertype": "LIMIT",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": str(price),
            "quantity": str(quantity)
        }
        
        try:
            order_id = self.api.placeOrder(orderparams)
            logger.info(f"Angel One Limit Order Placed: {side} {quantity} {ticker} @ {price} [ID: {order_id}]")
            return {
                "order_id": order_id,
                "ticker": ticker,
                "side": side,
                "status": "PENDING",
                "quantity": quantity,
                "price": price
            }
        except Exception as e:
            logger.error(f"Failed to place limit order for {ticker}: {e}")
            return {"status": "REJECTED", "reason": str(e)}

    def get_open_positions(self) -> List[Dict[str, Any]]:
        if not self.is_connected:
            return []
            
        try:
            response = self.api.position()
            if response['status'] and response['data']:
                positions = []
                for pos in response['data']:
                    net_qty = int(pos.get('netqty', 0))
                    if net_qty != 0: # Only return open positions
                        positions.append({
                            "ticker": pos.get('symbolname'), # E.g., 'SBIN'
                            "quantity": abs(net_qty),
                            "entry_price": float(pos.get('buyaverageprice') if net_qty > 0 else pos.get('sellaverageprice')),
                            "side": "LONG" if net_qty > 0 else "SHORT",
                            "unrealized_pnl": float(pos.get('pnl', 0.0))
                        })
                return positions
            return []
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return []

    def get_account_balance(self) -> float:
        if not self.is_connected:
            return 0.0
            
        try:
            response = self.api.rmsLimit()
            if response['status'] and response['data']:
                # 'net' represents net available margin
                return float(response['data'].get('net', 0.0))
            return 0.0
        except Exception as e:
            logger.error(f"Failed to fetch RMS limit: {e}")
            return 0.0
