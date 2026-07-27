import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def fetch_historical_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetches historical stock data from Yahoo Finance.
    """
    print(f"Fetching data for {ticker} from {start_date} to {end_date}...")
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, end=end_date)
    
    if df.empty:
        raise ValueError(f"No data found for ticker {ticker} in the given date range.")
    
    # Reset index to make Date a column instead of index, for easier JSON serialization later
    df.reset_index(inplace=True)
    
    # Ensure Date is string formatted as YYYY-MM-DD for consistency
    df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    
    return df

if __name__ == "__main__":
    # Test the function
    end = datetime.today().strftime('%Y-%m-%d')
    start = (datetime.today() - timedelta(days=365)).strftime('%Y-%m-%d')
    data = fetch_historical_data("AAPL", start, end)
    print(data.head())
