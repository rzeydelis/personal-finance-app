import plaid
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.api import plaid_api

# Your Plaid credentials (same as in get_bank_trx.py)
PLAID_CLIENT_ID = '687c2d7ed6586c002558aa90'
PLAID_SECRET = '51210e3ab65b3c5f4615e3ef9ea6ee'
PLAID_ENV = plaid.Environment.Production

# Initialize the Plaid client
configuration = plaid.Configuration(
    host=PLAID_ENV,
    api_key={
        'clientId': PLAID_CLIENT_ID,
        'secret': PLAID_SECRET,
    }
)

api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

def exchange_public_token(public_token):
    """
    Exchange a public_token from Plaid Link for an access_token
    
    Args:
        public_token: The public token received from Plaid Link
        
    Returns:
        access_token: Token to use for API calls
        item_id: Unique identifier for the Item
    """
    
    # Create the exchange request
    request = ItemPublicTokenExchangeRequest(
        public_token=public_token
    )
    
    try:
        # Exchange public token for access token
        response = client.item_public_token_exchange(request)
        access_token = response['access_token']
        item_id = response['item_id']
        
        print(f"Token exchange successful!")
        print(f"Access token: {access_token}")
        print(f"Item ID: {item_id}")
        print(f"\nUse this access_token in your get_bank_trx.py file.")
        
        return access_token, item_id
        
    except plaid.ApiException as e:
        print(f"Error exchanging token: {e}")
        return None, None

if __name__ == "__main__":
    # You'll get this public_token from Plaid Link on your frontend
    public_token = input("Enter the public_token from Plaid Link: ")
    
    if public_token:
        exchange_public_token(public_token) 