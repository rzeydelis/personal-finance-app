# Quick Start Guide

Get up and running with the Personal Finance App in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- pip package manager

## Installation (2 minutes)

```bash
# Clone the repository
git clone <your-repo-url>
cd personal-finance-app

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start with CSV (3 minutes)

The fastest way to try the app without any setup:

1. **Start the web server:**
   ```bash
   python src/web/app.py
   ```

2. **Open your browser:**
   - Navigate to `http://localhost:5000`

3. **Use the sample data:**
   - Look for the "Upload CSV" section
   - Click "Choose CSV File"
   - Select `sample_transactions.csv` from the project root
   - Click "Generate Tip from CSV"

4. **See your results:**
   - View personalized finance tips based on the sample data
   - Try the categorization page at `http://localhost:5000/categorize`

## Using Your Own Data

### From Your Bank's Website

Most banks allow you to export transactions:

1. Log into your online banking
2. Go to Account Details or Transactions
3. Look for "Export" or "Download" button
4. Choose CSV format
5. Select date range (last 90 days recommended)
6. Download the file

### Format Your CSV

Your CSV needs these columns:
- `date` - Transaction date (YYYY-MM-DD recommended)
- `name` or `merchant` - Transaction description
- `amount` - Transaction amount (positive for expenses, negative for income)

Optional:
- `account` - Account name

Example:
```csv
date,name,amount,account
2024-11-01,Starbucks Coffee,5.75,Credit Card
2024-11-02,Salary Deposit,-3000.00,Checking
2024-11-03,Electric Bill,125.00,Checking
```

### Upload and Analyze

1. Go to `http://localhost:5000`
2. Upload your CSV file
3. Click "Generate Tip from CSV"
4. View your personalized financial insights!

## Features to Try

### 1. Finance Tips (`/tip`)
Get AI-powered personalized finance advice:
- Spending pattern analysis
- Month-over-month comparisons
- Actionable savings recommendations
- Spending insights by category

### 2. Transaction Categorization (`/categorize`)
Automatically categorize your transactions:
- 11 standard categories (Food, Transportation, Shopping, etc.)
- Confidence scores for each categorization
- Filter and search functionality
- Export categorized data as CSV or JSON
- Category spending summaries

### 3. Plaid Integration (`/plaid-link`)
For automatic bank syncing (requires Plaid account):
- Connect directly to your bank
- Automatic transaction fetching
- Real-time data updates

## Configuration Options

### Lookback Period
Adjust how many days of transaction history to analyze (default: 90 days)

### Fetch Fresh Data
When using Plaid integration, this fetches the latest transactions from your bank

## Next Steps

- 📖 Read the [CSV Upload Guide](docs/CSV_UPLOAD_GUIDE.md) for detailed CSV formatting
- 🏦 Set up [Plaid Integration](docs/README.md#4-link-your-bank-account) for automatic syncing
- 🤖 Learn about [AI Categorization](docs/CATEGORIZATION_FEATURE_SUMMARY.md)

## Troubleshooting

### "No valid transactions found in CSV"
- Check that your CSV has headers: `date`, `name`, `amount`
- Verify date format (YYYY-MM-DD works best)
- Make sure amounts are numbers

### "Failed to read file"
- Ensure file is saved as CSV format (not Excel)
- Try opening in a text editor to verify it's plain text

### "Port already in use"
- Another app is using port 5000
- Stop the other app or change the port in `app.py`

### Need more help?
See [docs/CSV_UPLOAD_GUIDE.md](docs/CSV_UPLOAD_GUIDE.md) for comprehensive troubleshooting.

## Privacy Note

🔒 **Your data stays on your computer**
- CSV files are processed in memory only
- No data is stored permanently unless you use Plaid integration
- No external transmission except to your own Ollama/LLM instance

---

**Ready to dive deeper?** Check out the full [README](docs/README.md) for advanced features and Plaid setup.

