import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework.execution.angel_adapter import AngelOneBrokerAdapter

def check_cheap_stocks():
    load_dotenv()
    adapter = AngelOneBrokerAdapter(
        os.getenv("ANGELONE_API_KEY"),
        os.getenv("ANGELONE_CLIENT_CODE"),
        os.getenv("ANGELONE_PASSWORD"),
        os.getenv("ANGELONE_TOTP_SECRET")
    )
    
    if adapter.connect():
        print(f"💰 Account Balance: ₹{adapter.get_account_balance()}")
        
        # Test some penny stocks
        tickers_to_check = ['IDEA', 'YESBANK', 'SUZLON', 'GTLINFRA', 'VIKASLIFE']
        print("\nChecking live prices for cheap stocks:")
        
        for ticker in tickers_to_check:
            price = adapter.get_live_price(ticker)
            if price > 0:
                print(f"   {ticker}: ₹{price}")
                if price <= 20:
                    print(f"      ✅ You can afford {ticker}!")
                else:
                    print(f"      ❌ Too expensive for ₹20")
            else:
                print(f"   {ticker}: Not Found")

if __name__ == "__main__":
    check_cheap_stocks()
