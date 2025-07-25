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

### 4. Get Access Token

Before fetching transactions, you need an access token by linking a bank account:

```bash
# Start the Flask app
python src/web/app.py

# Or run the link token creation script
python src/api/link_token_create.py
```

## Usage

### Fetch Bank Transactions

```bash
python src/api/get_bank_trx.py
```

This will:
- Connect to your linked bank account
- Fetch transactions from the last 360 days
- Save results to a text file in the `data/` directory
- Display transaction summary in the console

### Run Web Application

```bash
python src/web/app.py
```

Visit `http://localhost:5000` to access the web interface.

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