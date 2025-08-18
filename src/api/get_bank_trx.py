import os
import plaid
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.api import plaid_api
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# 1. Load Plaid API configuration from environment variables
PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
PLAID_ENV_NAME = os.getenv('PLAID_ENV', 'sandbox')
ACCESS_TOKEN = os.getenv('PLAID_ACCESS_TOKEN')

# Map environment name to Plaid environment
env_mapping = {
    'sandbox': plaid.Environment.sandbox,
    'development': plaid.Environment.development,
    'production': plaid.Environment.production
}

PLAID_ENV = env_mapping.get(PLAID_ENV_NAME.lower(), plaid.Environment.production)

# Validate required environment variables
if not all([PLAID_CLIENT_ID, PLAID_SECRET, ACCESS_TOKEN]):
    raise ValueError(
        "Missing required environment variables. Please check your .env file.\n"
        "Required: PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ACCESS_TOKEN"
    )

# 2. Initialize the Plaid client
configuration = plaid.Configuration(
    host=PLAID_ENV,
    api_key={
        'clientId': PLAID_CLIENT_ID,
        'secret': PLAID_SECRET,
    }
)

api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

# 3. Define the date range for transactions
today = datetime.today()
start_date = (today - timedelta(days=360)).date() # Fetch transactions from the last 30 days
end_date = today.date()

# 4. Construct the request to retrieve transactions
request = TransactionsGetRequest(
    access_token=ACCESS_TOKEN,
    start_date=start_date,
    end_date=end_date,
    options=TransactionsGetRequestOptions() # Can include options like account_ids, count, offset
)

# 5. Make the API call and handle pagination
try:
    response = client.transactions_get(request)
    transactions = response.get('transactions', [])

    # Plaid returns paginated results, so loop to retrieve all transactions if needed
    while len(transactions) < response['total_transactions']:
        request.options.offset = len(transactions) # Update offset for the next page
        response = client.transactions_get(request)
        transactions.extend(response.get('transactions', []))

    # 6. Process the retrieved transactions and save to file
    output_filename = f"transactions_{start_date}_to_{end_date}.txt"
    
    with open(output_filename, 'w') as f:
        if transactions:
            header = f"Found {len(transactions)} transactions from {start_date} to {end_date}:\n"
            header += "=" * 60 + "\n\n"
            f.write(header)
            print(header.strip())
            
            for transaction in transactions:
                line = f"Date: {transaction.date}, Name: {transaction.name}, Amount: ${transaction.amount}\n"
                f.write(line)
                print(f"  {line.strip()}")
                
            summary = f"\n" + "=" * 60 + f"\nTotal transactions saved to: {output_filename}\n"
            f.write(summary)
            print(summary.strip())
        else:
            message = "No transactions found for the specified period.\n"
            f.write(message)
            print(message.strip())

except plaid.ApiException as e:
    print(f"Plaid API Error: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
