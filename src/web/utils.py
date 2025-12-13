import csv
import logging
from datetime import datetime
from io import StringIO

def parse_csv_transactions(csv_content):
    """Parse CSV content into structured transaction data
    
    Expected CSV formats (case-insensitive headers):
    - date, name/merchant/description, amount [, account]
    - date, time, name, description, amount [, account]
    
    Date formats supported: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, etc.
    Amount formats: with or without $ sign, negative or positive
    """
    transactions = []
    try:
        # Use StringIO to read CSV content
        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        if not reader.fieldnames:
            return {'success': False, 'transactions': [], 'count': 0, 'error': 'CSV file is empty or has no headers'}
        
        # Normalize header names (lowercase, strip whitespace)
        headers = {h.lower().strip(): h for h in reader.fieldnames if h}
        
        # Find required columns (case-insensitive)
        date_col = None
        name_col = None
        amount_col = None
        account_col = None
        time_col = None
        
        for col in headers.keys():
            if 'date' in col:
                date_col = headers[col]
            elif any(term in col for term in ['name', 'merchant', 'description', 'vendor']):
                if not name_col:  # Use first match
                    name_col = headers[col]
            elif 'amount' in col or 'total' in col:
                amount_col = headers[col]
            elif 'account' in col:
                account_col = headers[col]
            elif 'time' in col:
                time_col = headers[col]
        
        if not date_col or not amount_col:
            return {
                'success': False, 
                'transactions': [], 
                'count': 0, 
                'error': 'CSV must have "date" and "amount" columns'
            }
        
        if not name_col:
            # Try to find any text column for name
            for col in headers.keys():
                if col not in ['date', 'amount', 'account', 'time']:
                    name_col = headers[col]
                    break
        
        if not name_col:
            return {
                'success': False, 
                'transactions': [], 
                'count': 0, 
                'error': 'CSV must have a column for transaction name/merchant/description'
            }
        
        # Parse each row
        for i, row in enumerate(reader, 1):
            try:
                date_str = row.get(date_col, '').strip()
                name = row.get(name_col, '').strip() or 'Unknown'
                amount_str = row.get(amount_col, '').strip()
                account_name = row.get(account_col, '').strip() if account_col else None
                time_str = row.get(time_col, '').strip() if time_col else '12:00:00'
                
                if not date_str or not amount_str:
                    continue
                
                # Parse date - try multiple formats
                date_obj = None
                date_formats = [
                    '%Y-%m-%d',
                    '%m/%d/%Y',
                    '%d/%m/%Y',
                    '%Y/%m/%d',
                    '%m-%d-%Y',
                    '%d-%m-%Y',
                    '%b %d, %Y',
                    '%B %d, %Y',
                    '%d %b %Y',
                    '%d %B %Y',
                ]
                
                for fmt in date_formats:
                    try:
                        date_obj = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if not date_obj:
                    logging.warning(f"Could not parse date '{date_str}' in row {i}")
                    continue
                
                # Parse amount - remove $ and commas, handle negative
                amount_str = amount_str.replace('$', '').replace(',', '').strip()
                
                # Handle parentheses for negative amounts (accounting format)
                if amount_str.startswith('(') and amount_str.endswith(')'):
                    amount_str = '-' + amount_str[1:-1]
                
                try:
                    amount = float(amount_str)
                except ValueError:
                    logging.warning(f"Could not parse amount '{amount_str}' in row {i}")
                    continue
                
                transactions.append({
                    'id': len(transactions) + 1,
                    'date': date_obj.strftime('%Y-%m-%d'),
                    'datetime': date_obj,
                    'name': name,
                    'merchant': name,
                    'description': name,
                    'amount': amount,
                    'account_name': account_name,
                    'time': time_str
                })
            except Exception as e:
                logging.warning(f"Error parsing row {i}: {e}")
                continue
        
        if not transactions:
            return {
                'success': False,
                'transactions': [],
                'count': 0,
                'error': 'No valid transactions found in CSV. Check date and amount formats.'
            }
        
        return {'success': True, 'transactions': transactions, 'count': len(transactions), 'error': None}
    except Exception as e:
        logging.exception("Error parsing CSV")
        return {'success': False, 'transactions': [], 'count': 0, 'error': f'CSV parsing error: {str(e)}'}