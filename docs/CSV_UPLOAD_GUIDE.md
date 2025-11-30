# CSV Upload Feature Guide

## Overview
Users can now upload their own CSV transaction files to analyze their finances without needing Plaid integration or local transaction files.

## Supported File Formats

### CSV Format (Recommended)
Your CSV file should have headers and columns for transaction data.

**Required Columns:**
- `date` - Transaction date
- `name` or `merchant` or `description` - Transaction description
- `amount` - Transaction amount

**Optional Columns:**
- `account` - Account name
- `time` - Transaction time

### Example CSV Formats

#### Minimal Format
```csv
date,name,amount
2025-01-15,Starbucks,5.50
2025-01-16,Whole Foods,67.89
2025-01-17,Gas Station,45.00
```

#### With Account
```csv
date,merchant,amount,account
2025-01-15,Starbucks,5.50,Credit Card
2025-01-16,Whole Foods,67.89,Checking
2025-01-17,Gas Station,45.00,Credit Card
```

#### Full Format
```csv
date,time,name,description,amount,account
2025-01-15,08:30:00,Starbucks,Coffee,5.50,Credit Card
2025-01-16,14:22:00,Whole Foods,Groceries,67.89,Checking
2025-01-17,17:45:00,Shell,Gas,45.00,Credit Card
```

## Date Formats Supported

The CSV parser automatically detects these date formats:
- `2025-01-15` (YYYY-MM-DD) ✅ Recommended
- `01/15/2025` (MM/DD/YYYY)
- `15/01/2025` (DD/MM/YYYY)
- `2025/01/15` (YYYY/MM/DD)
- `01-15-2025` (MM-DD-YYYY)
- `15-01-2025` (DD-MM-YYYY)
- `Jan 15, 2025` (Mon DD, YYYY)
- `January 15, 2025` (Month DD, YYYY)
- `15 Jan 2025` (DD Mon YYYY)
- `15 January 2025` (DD Month YYYY)

## Amount Formats Supported

The parser handles various amount formats:
- `50.00` - Regular decimal
- `$50.00` - With dollar sign
- `1,234.56` - With comma separators
- `-50.00` - Negative amounts (income)
- `(50.00)` - Accounting format (treated as positive expense)

## Converting Text Files to CSV

If you have transaction data in text format like:
```
Date: 2025-10-26, Name: Starbucks, Amount: $3.00, Account: Credit Card
Date: 2025-10-27, Name: Target, Amount: $68.95, Account: Checking
```

You can convert it to CSV using the provided conversion tool or manually:

### Manual Conversion Steps
1. Create a new file with `.csv` extension
2. Add header row: `date,name,amount,account`
3. Convert each line to CSV format:
   - Remove `Date:`, `Name:`, `Amount:`, `Account:` labels
   - Remove `$` from amounts
   - Separate with commas
   - Result: `2025-10-26,Starbucks,3.00,Credit Card`

### Using Python Script
```python
import re

def convert_txt_to_csv(txt_content):
    """Convert text format to CSV"""
    lines = []
    pattern = r'Date: ([\d-]+), Name: ([^,]+), Amount: \$([+-]?[\d.]+)(?:, Account: ([^\n]+))?'
    
    for match in re.finditer(pattern, txt_content):
        date, name, amount, account = match.groups()
        account = account or 'Unknown'
        lines.append(f"{date},{name},{amount},{account}")
    
    return "date,name,amount,account\n" + "\n".join(lines)

# Usage
with open('transactions.txt', 'r') as f:
    txt_data = f.read()

csv_data = convert_txt_to_csv(txt_data)

with open('transactions.csv', 'w') as f:
    f.write(csv_data)
```

## How to Use CSV Upload

### In Finance Tip Page
1. Navigate to http://localhost:5000 (Finance Tip page)
2. Scroll to "Or Upload Your Own CSV" section
3. Click "Choose CSV File" button
4. Select your CSV file
5. Wait for "✅ CSV loaded successfully" message
6. Click "Generate Tip from CSV" button
7. View your personalized finance tip

### In Categorize Page
1. Navigate to http://localhost:5000/categorize
2. Find "Upload CSV Transactions (Optional)" section at top
3. Click "Choose CSV File" button
4. Select your CSV file
5. Wait for "✅ CSV loaded successfully" message
6. Click "Categorize CSV" button
7. View categorized transactions with summary

## Features Available with CSV Upload

All features work with uploaded CSV files:
- ✅ **Finance Tip Generation** - Get personalized spending advice
- ✅ **Transaction Categorization** - Auto-categorize all transactions
- ✅ **Spending Insights** - View category summaries and trends
- ✅ **Export Options** - Export categorized data as CSV or JSON
- ✅ **Filtering** - Filter by category or search merchants
- ✅ **OpenAI Integration** - Use cloud models for better analysis

## Privacy & Security

- **Your CSV data never leaves your browser** until you click Generate/Categorize
- **No automatic uploads** - You control when data is sent
- **No server-side storage** - CSV data is processed and discarded
- **Local processing** - If using Ollama, everything stays on your machine
- **HTTPS recommended** - Use HTTPS in production for encrypted transmission

## Troubleshooting

### "Please upload a CSV file" error
- **Cause:** File extension is not `.csv`
- **Solution:** Rename your file to end with `.csv`

### "CSV must have 'date' and 'amount' columns" error
- **Cause:** Missing required column headers
- **Solution:** Add header row with at least `date` and `amount` columns

### "No valid transactions found in CSV" error
- **Cause:** All rows failed to parse (date/amount format issues)
- **Solution:** Check date format and amount format match supported formats

### "Failed to read file" error
- **Cause:** File encoding issue or corrupted file
- **Solution:** Ensure file is UTF-8 encoded plain text CSV

## Best Practices

1. **Use consistent date format** - YYYY-MM-DD is most reliable
2. **Include headers** - Always have a header row
3. **Clean amounts** - Simple decimal numbers work best (e.g., `50.00`)
4. **Descriptive names** - Include merchant names for better categorization
5. **Account names** - Help track spending across accounts
6. **Test with small file first** - Verify format works before uploading all data

## Example: Bank Statement to CSV

Most banks provide CSV exports. If yours doesn't, here's how to create one:

### From Excel/Google Sheets
1. Open your bank statement in Excel/Google Sheets
2. Create columns: `date`, `name`, `amount`, `account`
3. Copy transaction data into these columns
4. File → Save As → CSV (Comma delimited)

### From PDF Statement
1. Copy transaction rows from PDF
2. Paste into spreadsheet
3. Use "Text to Columns" to separate into fields
4. Format as above and save as CSV

### From Online Banking
1. Log into your bank
2. Look for "Export" or "Download" options
3. Choose CSV format if available
4. If only PDF/OFX available, use conversion tool or manual entry

## Sample CSV File

Here's a complete example you can use as a template:

```csv
date,name,amount,account
2025-10-26,PATH TAPP PAYGO CP,3.00,Ultimate Rewards®
2025-10-26,Burlington,68.95,Ultimate Rewards®
2025-10-26,CVS,8.29,Ultimate Rewards®
2025-10-27,Au Bon Pain,1.49,Ultimate Rewards®
2025-10-27,ANIMAL INFIRMARY,266.43,TOTAL CHECKING
2025-10-28,DELIGHT GOURMET DELI,11.73,Ultimate Rewards®
2025-10-30,Trader Joe's,191.09,Ultimate Rewards®
2025-10-31,AlphaSense Salary,-3923.21,TOTAL CHECKING
2025-11-02,E-Z*PASSNY REBILL,350.00,Ultimate Rewards®
2025-11-02,AWS,19.68,Ultimate Rewards®
```

Save this as `sample_transactions.csv` and test the upload feature!

## Getting Help

If you encounter issues:
1. Check this guide for troubleshooting steps
2. Verify CSV format matches examples above
3. Try the sample CSV file to confirm app is working
4. Check browser console for detailed error messages
5. Review server logs for backend errors
