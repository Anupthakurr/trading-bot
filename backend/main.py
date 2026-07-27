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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
