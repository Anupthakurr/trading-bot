import sqlite3
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "live_trading.db"):
        self.db_path = db_path
        self._init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create tables if they don't exist."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY,
                balance REAL NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL,
                status TEXT NOT NULL,
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL, -- 'BUY' or 'SELL'
                order_type TEXT NOT NULL, -- 'MARKET' or 'LIMIT'
                quantity INTEGER NOT NULL,
                price REAL,
                status TEXT NOT NULL, -- 'PENDING', 'FILLED', 'REJECTED'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                filled_at TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER,
                ticker TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                pnl REAL NOT NULL,
                closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(position_id) REFERENCES positions(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for query in queries:
                    cursor.execute(query)
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def insert_log(self, level: str, message: str):
        with self.get_connection() as conn:
            conn.execute("INSERT INTO logs (level, message) VALUES (?, ?)", (level, message))
            conn.commit()
            
    def clear_logs(self):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM logs")
            conn.commit()
            
    def update_account_balance(self, balance: float):
        with self.get_connection() as conn:
            # Upsert logic for simple single row account tracking
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM account LIMIT 1")
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE account SET balance = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?", (balance, row['id']))
            else:
                cursor.execute("INSERT INTO account (id, balance) VALUES (1, ?)", (balance,))
            conn.commit()

    def get_account_balance(self) -> float:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM account LIMIT 1")
            row = cursor.fetchone()
            return row['balance'] if row else 0.0

    # Additional CRUD operations for the live dashboard API

    def get_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent orders, newest first."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, ticker, side, order_type, quantity, price, status, created_at, filled_at "
                "FROM orders ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_positions(self, status: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch positions, optionally filtered by status ('OPEN' or 'CLOSED')."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT id, ticker, quantity, entry_price, current_price, status, opened_at, updated_at "
                    "FROM positions WHERE status = ? ORDER BY id DESC LIMIT ?",
                    (status, limit)
                )
            else:
                cursor.execute(
                    "SELECT id, ticker, quantity, entry_price, current_price, status, opened_at, updated_at "
                    "FROM positions ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch recent engine logs, newest first."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, level, message, timestamp FROM logs ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent closed trades with P&L, newest first."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, position_id, ticker, entry_price, exit_price, quantity, pnl, closed_at "
                "FROM trades ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def sync_broker_positions(self, broker_positions: List[Dict[str, Any]]):
        """Reconcile local database positions with active broker positions."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Fetch all OPEN positions from DB
            cursor.execute("SELECT id, ticker, quantity, entry_price FROM positions WHERE status = 'OPEN'")
            db_open_positions = cursor.fetchall()
            
            broker_tickers = {p['ticker']: p for p in broker_positions}
            
            # 2. Close positions in DB that are no longer in broker
            for db_pos in db_open_positions:
                if db_pos['ticker'] not in broker_tickers:
                    # Broker no longer has this, mark as closed
                    conn.execute("UPDATE positions SET status = 'CLOSED', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (db_pos['id'],))
                    logger.info(f"Position for {db_pos['ticker']} closed in broker but was OPEN in DB. Marked as CLOSED.")
            
            # 3. Add positions from broker that are missing in DB
            db_tickers = {p['ticker'] for p in db_open_positions}
            for b_pos in broker_positions:
                if b_pos['ticker'] not in db_tickers:
                    # Insert into DB
                    conn.execute(
                        "INSERT INTO positions (ticker, quantity, entry_price, status) VALUES (?, ?, ?, ?)",
                        (b_pos['ticker'], b_pos['quantity'], b_pos['entry_price'], "OPEN")
                    )
                    logger.info(f"Position for {b_pos['ticker']} found in broker but missing in DB. Synced to DB.")
                    
            conn.commit()

