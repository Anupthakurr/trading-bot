import os
import sys
from dotenv import load_dotenv

# Add the backend directory to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from framework.execution.angel_adapter import AngelOneBrokerAdapter
import logging

logging.basicConfig(level=logging.INFO)

def test_connection():
    load_dotenv()
    
    api_key = os.getenv("ANGELONE_API_KEY")
    client_code = os.getenv("ANGELONE_CLIENT_CODE")
    password = os.getenv("ANGELONE_PASSWORD")
    totp_secret = os.getenv("ANGELONE_TOTP_SECRET")
    
    if not all([api_key, client_code, password, totp_secret]):
        print("Missing credentials in .env file.")
        return

    print(f"Testing connection for client: {client_code}")
    adapter = AngelOneBrokerAdapter(api_key, client_code, password, totp_secret)
    
    success = adapter.connect()
    
    if success:
        print("✅ Successfully connected to Angel One!")
        balance = adapter.get_account_balance()
        print(f"💰 Account Balance (Net Margin): ₹{balance}")
    else:
        print("❌ Failed to connect to Angel One. Please check your credentials.")

if __name__ == "__main__":
    test_connection()
