import plaid
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
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

def create_link_token(user_id='b63bc2870e2ae53385276c1780780153ddddb91c99cb5c2b15352490d1a00c34'):
    """
    Create a link token for Plaid Link initialization
    
    Args:
        user_id: A unique identifier for your user
        
    Returns:
        link_token: Token to initialize Plaid Link
    """
    
    # Create the request
    request = LinkTokenCreateRequest(
        products=[Products('transactions')],  # What data you want to access
        client_name="Personal Finance App",  # Your app name
        country_codes=[CountryCode('US')],  # Supported countries
        language='en',
        user=LinkTokenCreateRequestUser(client_user_id=user_id)
    )
    print(f"Request: {request}")
    
    try:
        # Create link token
        response = client.link_token_create(request)
        link_token = response['link_token']
        
        print(f"Link token created successfully!")
        print(f"Link token: {link_token}")
        print(f"\nUse this token to initialize Plaid Link in your frontend.")
        
        return link_token
        
    except plaid.ApiException as e:
        print(f"Error creating link token: {e}")
        return None


if __name__ == "__main__":
    create_link_token() 