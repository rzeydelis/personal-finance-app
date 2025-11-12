import requests
import pandas as pd
from io import StringIO
import logging

logging.basicConfig(level=logging.INFO)

def get_latest_30yr_mortgage_rate():
    """
    Fetch the latest 30-year mortgage rate from FRED.
    Returns a dictionary with date, rate, and any error information.
    """
    try:
        # FRED CSV export URL for the MORTGAGE30US series
        csv_url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US'
        
        # Fetch the CSV data
        resp = requests.get(csv_url)
        resp.raise_for_status()  # ensure we notice bad responses
        
        # Load into pandas
        df = pd.read_csv(StringIO(resp.text))
        
        # Drop any missing values and grab the last row
        df = df.dropna(subset=['MORTGAGE30US'])
        latest = df.iloc[-1]
        
        # Extract date and value
        date = latest['observation_date']
        rate = float(latest['MORTGAGE30US'])
        
        return {
            'success': True,
            'date': date,
            'rate': rate,
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'date': None,
            'rate': None,
            'error': str(e)
        }
