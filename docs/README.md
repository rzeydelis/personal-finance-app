# Personal Finance App

A comprehensive personal finance application that integrates with Plaid API to fetch and analyze bank transactions, built with Flask and Python.

## Features

- 🏦 **Bank Integration**: Connect to your bank accounts via Plaid API
- 📊 **Transaction Analysis**: Fetch and analyze your transaction history
- 🏠 **Mortgage Analysis**: Tools for mortgage rate analysis and tracking
- 🔐 **Secure Configuration**: Environment-based configuration for API keys
- 🌐 **Web Interface**: Flask-based web application with user-friendly interface

## Project Structure

```
personal-finance-app/
├── src/
│   ├── api/                    # Plaid API integration scripts
│   │   ├── get_bank_trx.py    # Main transaction fetching script
│   │   ├── exchange_token.py   # Token exchange utilities
│   │   ├── link_token_create.py # Link token creation
│   │   └── get_mortgage_rate.py # Mortgage rate utilities
│   └── web/                    # Web application
│       ├── app.py             # Flask application
│       ├── templates/         # HTML templates
│       └── plaid_link_demo.html # Plaid Link demo page
├── static/                     # Static web assets
├── data/                      # Transaction data files (gitignored)
├── docs/                      # Documentation
├── scripts/                   # Utility scripts
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
└── .gitignore                # Git ignore rules
```

## Setup & Installation

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd personal-finance-app
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` file with your actual Plaid credentials:

```bash
# Get these from your Plaid Dashboard (https://dashboard.plaid.com/)
PLAID_CLIENT_ID=your_actual_client_id
PLAID_SECRET=your_actual_secret
PLAID_ENV=sandbox  # Use 'sandbox' for testing, 'production' for live data
```

### 3. Plaid Account Setup

1. Sign up for Plaid Developer account: https://dashboard.plaid.com/
2. Create a new application
3. Copy your `client_id` and `secret` keys
4. Set appropriate allowed products and countries

### 4. Link Your Bank Account

Before fetching live transactions you must complete the Plaid Link flow to obtain an access token:

1. Create a Link token (launches the Plaid Link modal in your frontend):
   ```bash
   python src/api/bank_data_pipeline.py --link your_user_id
   ```
2. Complete the Plaid Link workflow in the browser and capture the resulting `public_token`.
3. Exchange the public token for an access token:
   ```bash
   python src/api/bank_data_pipeline.py public-sandbox-abc123...
   ```
   The helper will print the `access_token` and also persist it to `data/plaid_access_tokens.json` for reuse.
4. Copy the printed access token into your `.env` file as `PLAID_ACCESS_TOKEN`, or leave it in the token store if you prefer not to keep secrets in environment variables.

💡 Access tokens always follow the format `access-<environment>-<identifier>`. If you see a Plaid error about an invalid token format, re-run the exchange step above.

## Usage

### Fetch Bank Transactions

```bash
# Fetch the last 90 days (default)
python src/api/get_bank_trx.py

# Specify a custom range
python src/api/get_bank_trx.py 2024-08-01 2024-09-01

# Or use a rolling window
python src/api/get_bank_trx.py --days 30
```

The exporter now:
- Reuses access tokens stored in `.env` or `data/plaid_access_tokens.json`
- Filters to specific accounts when you set `PLAID_ACCOUNT_NAME_FILTER`, `PLAID_ACCOUNT_IDS`, or `PLAID_ACCOUNT_SUBTYPES`
- Saves results to `data/transactions_<start>_to_<end>.txt`
- Surfaces actionable error messages if credentials are missing or invalid

Example for Chase-only exports:

```bash
# .env
PLAID_ACCOUNT_NAME_FILTER=chase
```

### Run Web Application

```bash
python src/web/app.py
```

Visit `http://localhost:5000` to access the web interface.

The dashboard now includes a **Connect Plaid Access** panel—paste either a freshly exchanged Plaid access token or the public token you just received from Plaid Link. The app will store it locally (in `data/plaid_access_tokens.json`) so one click can refresh your Chase transactions.

### Mortgage Rate Analysis

```bash
python src/api/get_mortgage_rate.py
```

## Security Notes

⚠️ **Important Security Practices:**

- **Never commit API keys**: The `.env` file is gitignored for security
- **Use Sandbox Environment**: Start with `PLAID_ENV=sandbox` for testing
- **Rotate Keys Regularly**: Regenerate API keys periodically
- **Limit Access**: Use environment-specific keys with minimal required permissions
- **Token store**: Exchanged access tokens are cached in `data/plaid_access_tokens.json` (gitignored). Treat this file as sensitive.

## API Documentation

- **Plaid API Docs**: https://plaid.com/docs/
- **Plaid Python Library**: https://github.com/plaid/plaid-python

## Troubleshooting

### Common Issues

1. **Missing Environment Variables**
   ```
   Error: Missing required environment variables
   ```
   Solution: Ensure your `.env` file has all required variables set.

2. **Invalid Access Token**
   ```
   Error: INVALID_ACCESS_TOKEN
   ```
   Solution: Generate a new access token using the link token flow.

3. **API Rate Limits**
   ```
   Error: RATE_LIMIT_EXCEEDED
   ```
   Solution: Implement exponential backoff or reduce request frequency.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests if applicable
5. Commit changes: `git commit -am 'Add feature'`
6. Push to branch: `git push origin feature-name`
7. Submit a Pull Request

## License

This project is for personal use. Please review Plaid's terms of service for API usage guidelines.

## Support

For issues related to:
- **Plaid API**: Check [Plaid Documentation](https://plaid.com/docs/) or [Support](https://plaid.com/support/)
- **This Application**: Open an issue in this repository
