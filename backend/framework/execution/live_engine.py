import time
import logging
import threading
from typing import Dict, Any, Optional
import datetime

from framework.strategies.base import Strategy, Signal
from framework.data.provider import DataProvider
from framework.data.timeframes import Timeframe
from framework.execution.broker_adapter import BrokerAdapter
from framework.execution.db import DatabaseManager

logger = logging.getLogger(__name__)

class LiveEngine:
    """
    Live event-driven trading engine.
    Loops indefinitely, queries broker/data, evaluates strategy, executes trades.
    """

    def __init__(
        self,
        strategy: Strategy,
        data_provider: DataProvider,
        broker: BrokerAdapter,
        db: DatabaseManager,
        ticker: str,
        interval_seconds: int = 60,
        risk_per_trade: float = 0.01,
        timeframe: Timeframe = Timeframe.M1
    ):
        self.strategy = strategy
        self.data_provider = data_provider
        self.broker = broker
        self.db = db
        self.ticker = ticker
        self.interval = interval_seconds
        self.risk_per_trade = risk_per_trade
        self.timeframe = timeframe
        
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        
        self.max_daily_loss = 0.05
        self.max_trades_per_day = 10
        self.trades_today = 0
        self.daily_start_balance = 0.0

    def start(self):
        if self.is_running:
            logger.warning("Live engine is already running.")
            return
            
        logger.info(f"Starting live engine for {self.ticker} on {self.interval}s interval")
        self.is_running = True
        
        # Connect to broker
        if not self.broker.connect():
            error_msg = "Failed to connect to broker. Check your API credentials. Aborting."
            logger.error(error_msg)
            self.is_running = False
            raise ConnectionError(error_msg)
            
        # Log initial balance
        bal = self.broker.get_account_balance()
        self.db.update_account_balance(bal)
        self.daily_start_balance = bal
        self.trades_today = 0
        self.db.insert_log("INFO", f"Live engine started. Initial Balance: {bal}")
        
        # Sync positions
        logger.info("Synchronizing positions with broker...")
        open_positions = self.broker.get_open_positions()
        self.db.sync_broker_positions(open_positions)
        
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        logger.info("Stopping live engine...")
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.db.insert_log("INFO", "Live engine stopped.")

    def is_market_open(self) -> bool:
        try:
            import pytz
        except ImportError:
            return True # fallback if pytz not installed
            
        tz = pytz.timezone('Asia/Kolkata')
        now = datetime.datetime.now(tz)
        if now.weekday() >= 5: # 5=Sat, 6=Sun
            return False
        
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return market_open <= now <= market_close

    def _loop(self):
        while self.is_running:
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Error in live tick: {e}")
                self.db.insert_log("ERROR", f"Tick error: {e}")
                
            # Sleep for the interval
            for _ in range(self.interval):
                if not self.is_running:
                    break
                time.sleep(1)

    def _tick(self):
        if not self.is_market_open():
            logger.debug("Market is closed. Skipping tick.")
            return

        logger.debug(f"Tick: Evaluating strategy for {self.ticker}")
        
        # Check daily loss limit
        current_bal = self.broker.get_account_balance()
        if self.daily_start_balance > 0:
            daily_loss_pct = (self.daily_start_balance - current_bal) / self.daily_start_balance 
            if daily_loss_pct >= self.max_daily_loss:
                msg = f"Max daily loss reached ({daily_loss_pct*100:.2f}% >= {self.max_daily_loss*100:.2f}%). Trading halted for today."
                logger.warning(msg)
                self.db.insert_log("WARNING", msg)
                return
        
        # 1. Fetch recent data (e.g., last 10 days)
        end = datetime.datetime.now().strftime("%Y-%m-%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=10)).strftime("%Y-%m-%d")
        
        try:
            df = self.data_provider.fetch(self.ticker, self.timeframe, start, end)
        except ValueError as e:
            logger.error(f"Data fetch error: {e}")
            return
            
        if df.empty or len(df) < 50:
            msg = f"Not enough data to calculate indicators for {self.ticker}. (Need 50 bars)"
            logger.warning(msg)
            self.db.insert_log("WARNING", msg)
            return

        # 2. Pre-calculate indicators
        df = self.strategy.init(df)
        
        # 3. Get signal for the *last* fully closed bar
        last_idx = len(df) - 1
        signal = self.strategy.next(last_idx, df)
        
        # 4. Check current open positions from broker
        open_positions = self.broker.get_open_positions()
        has_position = any(p['ticker'] == self.ticker for p in open_positions)
        my_position = next((p for p in open_positions if p['ticker'] == self.ticker), None)
        
        current_price = self.broker.get_live_price(self.ticker)
        
        # 5. Stop Loss / Trailing Stop checking
        if my_position:
            entry = my_position['entry_price']
            atr = 0.0
            if 'ATR' in df.columns:
                atr = df['ATR'].iloc[-1]
                
            # ATR Trailing Stop (simplified) or static stop
            sl_price = entry - (atr * 2.0) if atr > 0 else entry * 0.98
            
            if current_price <= sl_price:
                msg = f"STOP LOSS HIT for {self.ticker} at {current_price} (SL: {sl_price:.2f})"
                logger.warning(msg)
                self.db.insert_log("WARNING", msg)
                signal = Signal(Signal.SELL)

        # 6. Execute Signals
        if signal.action == Signal.BUY and not has_position:
            if self.trades_today >= self.max_trades_per_day:
                logger.warning(f"Max trades per day ({self.max_trades_per_day}) reached. Skipping BUY.")
                return

            capital = self.broker.get_account_balance()
            risk_amt = capital * self.risk_per_trade
            qty = max(1, int(risk_amt / current_price))
            
            logger.info(f"Executing BUY for {qty} {self.ticker} @ {current_price}")
            resp = self.broker.place_market_order(self.ticker, "BUY", qty)
            
            if resp.get("status") == "FILLED":
                self.trades_today += 1
                with self.db.get_connection() as conn:
                    conn.execute(
                        "INSERT INTO orders (ticker, side, order_type, quantity, price, status) VALUES (?, ?, ?, ?, ?, ?)",
                        (self.ticker, "BUY", "MARKET", qty, current_price, "FILLED")
                    )
                    conn.execute(
                        "INSERT INTO positions (ticker, quantity, entry_price, status) VALUES (?, ?, ?, ?)",
                        (self.ticker, qty, current_price, "OPEN")
                    )
                    conn.commit()
                self.db.insert_log("INFO", f"ORDER BUY {self.ticker} {qty} shares FILLED at {current_price}")
            elif resp.get("status") == "REJECTED":
                reason = resp.get("reason", "Unknown")
                logger.error(f"Order REJECTED: {reason}")
                self.db.insert_log("ERROR", f"ORDER BUY {self.ticker} REJECTED: {reason}")
                
        elif signal.action == Signal.SELL and has_position:
            qty = my_position['quantity']
            logger.info(f"Executing SELL for {qty} {self.ticker} @ {current_price}")
            resp = self.broker.place_market_order(self.ticker, "SELL", qty)
            
            if resp.get("status") == "FILLED":
                with self.db.get_connection() as conn:
                    conn.execute(
                        "INSERT INTO orders (ticker, side, order_type, quantity, price, status) VALUES (?, ?, ?, ?, ?, ?)",
                        (self.ticker, "SELL", "MARKET", qty, current_price, "FILLED")
                    )
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, entry_price FROM positions WHERE ticker = ? AND status = 'OPEN' ORDER BY id DESC LIMIT 1", (self.ticker,))
                    pos = cursor.fetchone()
                    pnl = 0.0
                    if pos:
                        pnl = (current_price - pos['entry_price']) * qty
                        conn.execute("UPDATE positions SET status = 'CLOSED', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (pos['id'],))
                        conn.execute(
                            "INSERT INTO trades (position_id, ticker, entry_price, exit_price, quantity, pnl) VALUES (?, ?, ?, ?, ?, ?)",
                            (pos['id'], self.ticker, pos['entry_price'], current_price, qty, pnl)
                        )
                    conn.commit()
                self.db.insert_log("INFO", f"ORDER SELL {self.ticker} {qty} shares FILLED at {current_price}. PnL: {pnl:.2f}")
            elif resp.get("status") == "REJECTED":
                reason = resp.get("reason", "Unknown")
                logger.error(f"Order REJECTED: {reason}")
                self.db.insert_log("ERROR", f"ORDER SELL {self.ticker} REJECTED: {reason}")
        else:
            # Heartbeat log so UI shows activity
            self.db.insert_log("INFO", f"Evaluated tick. Price: {current_price}. Signal: {signal.action.name}")

        # Update balance
        bal = self.broker.get_account_balance()
        self.db.update_account_balance(bal)
