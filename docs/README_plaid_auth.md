# Plaid Access Token Generation Guide

This guide explains how to generate an access token for the Plaid API to retrieve bank transaction data.

## Important Note

The documentation you referenced (`https://plaid.com/plaid-exchange/docs/authentication/`) is for **Plaid Exchange**, which is designed for financial institutions implementing OAuth to connect TO Plaid. 

Your current setup uses the **standard Plaid API**, which allows applications to connect to banks THROUGH Plaid. The authentication flow is different.

## Standard Plaid API Authentication Flow

```
1. Create Link Token (Backend) → 2. Initialize Plaid Link (Frontend) → 3. Get Public Token → 4. Exchange for Access Token → 5. Use Access Token for API calls
```

## Step-by-Step Process

### Step 1: Create a Link Token
Run the backend script to generate a link token:

```bash
python link_token_create.py
```

This will output a link token that looks like: `link-sandbox-12345678-1234-1234-1234-123456789012`

### Step 2: Use Plaid Link (Frontend)
1. Open `plaid_link_demo.html` in your browser
2. Paste the link token from Step 1
3. Click "Connect Bank Account"
4. Use these Sandbox test credentials:
   - **Username:** `user_good`
   - **Password:** `pass_good`
   - **PIN:** `1234` (if asked)

### Step 3: Exchange Public Token for Access Token
After successfully connecting through Plaid Link, you'll get a public token. Use it to get your access token:

```bash
python exchange_token.py
```

Enter the public token when prompted. This will output an access token.

### Step 4: Use the Access Token
Copy the access token and update it in `get_bank_trx.py`:

```python
ACCESS_TOKEN = 'access-sandbox-your-actual-token-here'
```

Then run your transaction script:

```bash
python get_bank_trx.py
```

## Files Overview

- **`link_token_create.py`** - Creates link tokens for Plaid Link initialization
- **`plaid_link_demo.html`** - Frontend demo for Plaid Link integration
- **`exchange_token.py`** - Exchanges public tokens for access tokens
- **`get_bank_trx.py`** - Your existing script to fetch transactions (now with proper access token)

## Security Best Practices

1. **Never expose credentials in frontend code** - Link tokens are safe for frontend use, but keep client secrets on the backend
2. **Store access tokens securely** - In production, store access tokens in a secure database, not in source code
3. **Use environment variables** - For production, load credentials from environment variables:

```python
import os
PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
```

## Production vs Sandbox

- **Sandbox**: Use `plaid.Environment.Sandbox` for testing
- **Production**: Use `plaid.Environment.Production` for live data
- **Development**: Use `plaid.Environment.Development` for development testing

## Troubleshooting

### Common Issues:

1. **"Invalid credentials"** - Check your client ID and secret
2. **"Invalid link token"** - Link tokens expire after 30 minutes, generate a new one
3. **"Item login required"** - The user needs to re-authenticate through Plaid Link
4. **"Insufficient permissions"** - Ensure your Plaid account has access to the products you're requesting

### Error Codes:
- `INVALID_CREDENTIALS` - Wrong client ID or secret
- `INVALID_ACCESS_TOKEN` - Access token is invalid or expired
- `ITEM_LOGIN_REQUIRED` - User needs to re-link their account
- `RATE_LIMIT_EXCEEDED` - Too many API requests

## Next Steps

Once you have a working access token:

1. **Store multiple tokens** - Users can connect multiple bank accounts
2. **Handle token rotation** - Access tokens can expire and need refresh
3. **Implement webhooks** - Get notifications when account data changes
4. **Add error handling** - Handle various Plaid API errors gracefully

## Resources

- [Plaid API Reference](https://plaid.com/docs/api/)
- [Plaid Link Guide](https://plaid.com/docs/link/)
- [Python Quickstart](https://plaid.com/docs/quickstart/) 