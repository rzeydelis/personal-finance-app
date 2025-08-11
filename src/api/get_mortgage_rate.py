import requests
import pandas as pd
from io import StringIO
import logging

logging.basicConfig(level=logging.INFO)

def get_latest_30yr_mortgage_rate():
    # FRED CSV export URL for the MORTGAGE30US series
    csv_url = 'hc'
    
    # Fetch the CSV data
    resp = requests.get(csv_url)
    resp.raise_for_status()  # ensure we notice bad responses
    
    # print(f"resp.text: {resp.text}")
    # print(f"type of resp.text: {type(resp.text)}")
    # Load into pandas
    df = pd.read_csv(StringIO(resp.text))
    
    # Drop any missing values and grab the last row
    df = df.dropna(subset=['MORTGAGE30US'])
    latest = df.iloc[-1]
    
    # Extract date and value
    date = latest['observation_date']
    rate = latest['MORTGAGE30US']
    logging.info(f"Latest 30‑Year Fixed Mortgage Rate (U.S.) as of {date}: {rate:.2f}%")
    # print(f"Latest 30‑Year Fixed Mortgage Rate (U.S.) as of {date}: {rate:.2f}%")

if __name__ == '__main__':
    get_latest_30yr_mortgage_rate()
