from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import uvicorn

from data import fetch_historical_data
from engine import run_backtest

app = FastAPI(title="Quant Backtesting Engine API")

# Enable CORS so the React frontend can talk to it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BacktestRequest(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    short_window: int = 20
    long_window: int = 50
    initial_capital: float = 100000.0
    strategy_version: int = 1
    rsi_period: int = 14
    atr_multiplier: float = 2.0
    risk_per_trade: float = 0.01

@app.get("/")
def read_root():
    return {"message": "Quant Engine is running!"}

@app.post("/api/backtest")
def run_strategy(request: BacktestRequest):
    try:
        # 1. Fetch Data
        df = fetch_historical_data(request.ticker, request.start_date, request.end_date)
        
        # 2. Run Backtest
        results = run_backtest(
            df=df, 
            strategy_version=request.strategy_version,
            short_window=request.short_window, 
            long_window=request.long_window,
            rsi_period=request.rsi_period,
            atr_multiplier=request.atr_multiplier,
            risk_per_trade=request.risk_per_trade,
            initial_capital=request.initial_capital
        )
        
        return results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

from framework.execution.live_engine import LiveEngine
from framework.execution.mock_adapter import MockBrokerAdapter
from framework.execution.angel_adapter import AngelOneBrokerAdapter
from framework.execution.db import DatabaseManager
from framework.data.provider import YFinanceProvider
from framework.data.timeframes import Timeframe
from framework.strategies.adapter import get_strategy

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Global state to hold our active live engines (in a production app, use Celery/Redis)
active_engines = {}
db_manager = DatabaseManager("live_trading.db")

class LiveTradeRequest(BaseModel):
    ticker: str
    strategy_version: int = 1
    interval_seconds: int = 60
    risk_per_trade: float = 0.01
    broker: str = "mock"

@app.post("/api/live/start")
def start_live_trading(request: LiveTradeRequest):
    if request.ticker in active_engines:
        raise HTTPException(status_code=400, detail="Engine already running for this ticker")
        
    try:
        # Construct dependencies
        strategy = get_strategy(f"v{request.strategy_version}", {})
        provider = YFinanceProvider()
        
        # Select Broker Adapter
        if request.broker.lower() == "angelone":
            api_key = os.getenv("ANGELONE_API_KEY")
            client_code = os.getenv("ANGELONE_CLIENT_CODE")
            password = os.getenv("ANGELONE_PASSWORD")
            totp_secret = os.getenv("ANGELONE_TOTP_SECRET")
            
            if not all([api_key, client_code, password, totp_secret]):
                raise ValueError("Angel One credentials missing in .env file")
                
            broker = AngelOneBrokerAdapter(
                api_key=api_key,
                client_code=client_code,
                password=password,
                totp_secret=totp_secret
            )
        else:
            broker = MockBrokerAdapter(initial_balance=100000.0)
        
        engine = LiveEngine(
            strategy=strategy,
            data_provider=provider,
            broker=broker,
            db=db_manager,
            ticker=request.ticker,
            interval_seconds=request.interval_seconds,
            risk_per_trade=request.risk_per_trade,
            timeframe=Timeframe.M1
        )
        
        engine.start()
        active_engines[request.ticker] = engine
        
        broker_name = "Angel One" if request.broker.lower() == "angelone" else "Mock Broker"
        return {"message": f"Live trading started for {request.ticker} using {broker_name}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/live/stop")
def stop_live_trading(ticker: str):
    if ticker not in active_engines:
        raise HTTPException(status_code=404, detail="No active engine found for this ticker")
        
    engine = active_engines.pop(ticker)
    engine.stop()
    return {"message": f"Live trading stopped for {ticker}."}

@app.get("/api/live/status")
def get_live_status():
    """Return which tickers have active engines and their connection info."""
    engines_info = {}
    for ticker, engine in active_engines.items():
        engines_info[ticker] = {
            "is_running": engine.is_running,
            "interval_seconds": engine.interval,
            "strategy": engine.strategy.name if hasattr(engine.strategy, 'name') else "Unknown",
            "risk_per_trade": engine.risk_per_trade,
        }
    return {
        "active_engines": engines_info,
        "total_active": len(active_engines),
    }

@app.get("/api/live/balance")
def get_live_balance():
    """Return current account balance from the database."""
    balance = db_manager.get_account_balance()
    return {"balance": balance}

@app.get("/api/live/positions")
def get_live_positions(status: str = None, limit: int = 50):
    """Return positions, optionally filtered by status."""
    positions = db_manager.get_positions(status=status, limit=limit)
    return {"positions": positions}

@app.get("/api/live/orders")
def get_live_orders(limit: int = 50):
    """Return recent orders."""
    orders = db_manager.get_orders(limit=limit)
    return {"orders": orders}

@app.get("/api/live/logs")
def get_live_logs(limit: int = 100):
    """Return recent engine logs."""
    logs = db_manager.get_logs(limit=limit)
    return {"logs": logs}

@app.post("/api/live/clear_logs")
def clear_live_logs():
    """Clear all engine logs."""
    db_manager.clear_logs()
    return {"message": "Logs cleared successfully."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
