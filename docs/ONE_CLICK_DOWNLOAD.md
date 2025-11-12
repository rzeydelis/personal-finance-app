# One-Click Bank Data Download Pipeline

This feature provides a seamless, secure way for users to download their bank transaction data with a single click. It implements the complete Plaid token flow according to their official documentation and best practices.

## 🏗️ Architecture Overview

The pipeline consists of several components working together:

### 1. **Token Flow (Plaid Standard)**
```
Link Token → Public Token → Access Token → Bank Data
```

### 2. **Core Components**

#### **BankDataPipeline Class** (`src/api/bank_data_pipeline.py`)
- **Purpose**: Unified pipeline handling all Plaid token operations
- **Key Methods**:
  - `create_link_token()` - Creates link tokens for Plaid Link initialization
  - `exchange_public_token()` - Exchanges public tokens for access tokens
  - `get_transactions()` - Retrieves bank transactions using access token
  - `one_click_download()` - Complete pipeline from public token to formatted data

#### **Flask API Endpoints** (`src/web/app.py`)
- **`/api/create-link-token`** - Creates link tokens for frontend
- **`/api/one-click-download`** - Handles complete download pipeline
- **`/api/download-file`** - Serves formatted data for download

#### **Frontend Interface** (`src/web/one_click_download.html`)
- **Beautiful, modern UI** with step-by-step guidance
- **Real-time progress tracking** with visual feedback
- **Multiple download formats** (JSON, CSV, TXT)
- **Secure Plaid Link integration**

## 🔐 Security Implementation

### **Token Handling (Per Plaid Best Practices)**
- **Link Token**: Short-lived, client-safe, used for Plaid Link initialization
- **Public Token**: Short-lived, client-safe, exchanged for access token
- **Access Token**: Long-lived, server-only, used for API calls
- **Environment Variables**: All credentials stored securely in `.env`

### **Data Flow Security**
1. Link token created server-side with user ID
2. Public token received from Plaid Link (client-side)
3. Public token immediately exchanged for access token (server-side)
4. Access token used to fetch data (server-side only)
5. Formatted data returned to client for download

## 📋 Required Environment Variables

Create a `.env` file in your project root:

```env
# Plaid Credentials
PLAID_CLIENT_ID=your_client_id_here
PLAID_SECRET=your_secret_here
PLAID_ENV=sandbox  # or 'production'

# Optional: Pre-existing access token for direct API calls
PLAID_ACCESS_TOKEN=your_access_token_here
```

## 🚀 Usage

### **Option 1: Web Interface (Recommended)**
1. Start the Flask app: `python src/web/app.py`
2. Navigate to: `http://localhost:5000/one-click-download`
3. Follow the guided interface:
   - Configure download settings
   - Connect your bank account
   - Download your data instantly

### **Option 2: API Integration**

#### Create Link Token
```bash
curl -X POST http://localhost:5000/api/create-link-token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "your_user_123"}'
```

#### One-Click Download
```bash
curl -X POST http://localhost:5000/api/one-click-download \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your_user_123",
    "public_token": "public-token-from-plaid-link",
    "days_back": 90,
    "format": "json"
  }'
```

### **Option 3: Python SDK**
```python
from src.api.bank_data_pipeline import BankDataPipeline

# Initialize pipeline
pipeline = BankDataPipeline()

# Create link token
link_token = pipeline.create_link_token("user_123")

# After user completes Plaid Link and you get public_token:
result = pipeline.one_click_download(
    user_id="user_123",
    public_token="public-token-from-plaid-link",
    days_back=90,
    format="json"
)

if result['success']:
    # Save the formatted data
    with open(result['filename'], 'w') as f:
        f.write(result['data'])
```

## 📊 Download Formats

### **JSON Format**
```json
{
  "metadata": {
    "generated_at": "2025-10-12T...",
    "total_transactions": 45,
    "total_amount": -2347.89
  },
  "transactions": [
    {
      "date": "2025-10-11",
      "name": "Starbucks Coffee",
      "amount": -4.95,
      "category": ["Food and Drink", "Restaurants"],
      "account_id": "acc_123...",
      "transaction_id": "txn_456..."
    }
  ]
}
```

### **CSV Format**
```csv
date,name,amount,account_id,category,transaction_id,merchant_name,location
2025-10-11,Starbucks Coffee,-4.95,acc_123,"['Food and Drink', 'Restaurants']",txn_456,Starbucks,"{""city"": ""San Francisco""}"
```

### **TXT Format**
```
Bank Transactions Report - Generated 2025-10-12 14:30:15
================================================================================

  1. 2025-10-11 | Starbucks Coffee              | $  -4.95
     Category: Food and Drink, Restaurants

  2. 2025-10-10 | Amazon Purchase               | $ -29.99
     Category: Shops, Online Marketplaces

================================================================================
Total Transactions: 45
Total Amount: $-2347.89
```

## 🔧 Configuration Options

### **Date Ranges**
- Last 30 days
- Last 90 days (default)
- Last 6 months
- Last year
- Custom range (via API)

### **Supported Formats**
- **JSON**: Structured data for applications
- **CSV**: Spreadsheet-compatible format
- **TXT**: Human-readable format

## 🏛️ Plaid Integration Details

### **Environments Supported**
- **Sandbox**: For testing with fake data
- **Production**: For real bank connections

### **Products Used**
- **Transactions**: Retrieves transaction history
- **Auth**: Account and routing number access (future)
- **Identity**: Account holder information (future)

### **Supported Countries**
- United States (US)
- Canada (CA) - with configuration
- United Kingdom (GB) - with configuration

## 🛠️ Error Handling

The pipeline includes comprehensive error handling:

### **Common Error Scenarios**
1. **Invalid Credentials**: Clear error messages for missing/invalid API keys
2. **Token Exchange Failures**: Handles expired or invalid public tokens
3. **API Rate Limits**: Implements retry logic with exponential backoff
4. **Network Issues**: Graceful degradation with user-friendly messages
5. **Data Format Errors**: Validates all data before processing

### **Error Response Format**
```json
{
  "success": false,
  "error": "Description of what went wrong",
  "step": "token_exchange|fetch_transactions|pipeline_execution",
  "timestamp": "2025-10-12T..."
}
```

## 🧪 Testing

### **Sandbox Testing**
Use these test credentials in Sandbox mode:
- **Username**: `user_good`
- **Password**: `pass_good`
- **PIN**: `1234` (if requested)

### **Test Flow**
1. Set `PLAID_ENV=sandbox` in your `.env`
2. Use the web interface at `/one-click-download`
3. Connect using sandbox credentials
4. Download test transaction data

## 📈 Performance Optimizations

### **Implemented Optimizations**
- **Pagination Handling**: Automatically handles large transaction sets
- **Memory Efficient**: Streams data instead of loading everything in memory
- **Caching**: Link tokens cached to avoid unnecessary API calls
- **Async Processing**: Background processing for large datasets

### **Scalability Considerations**
- **Database Storage**: Consider storing access tokens for repeat users
- **Queue Processing**: For bulk downloads, implement job queues
- **CDN Integration**: Serve download files via CDN for large datasets

## 🔍 Monitoring & Logging

### **Built-in Logging**
- All API calls logged with timestamps
- Error tracking with detailed stack traces
- Performance metrics for each pipeline step
- User activity tracking (anonymized)

### **Log Format Example**
```
✅ BankDataPipeline initialized with environment: sandbox
✅ Link token created successfully for user: user_123
📅 Fetching transactions from 2025-07-13 to 2025-10-12
✅ Retrieved 45 transactions
🚀 Starting one-click bank data download for user: user_123
✅ Pipeline completed successfully! Generated bank_transactions_20251012_143015.json
```

## 🚀 Deployment

### **Production Checklist**
- [ ] Set `PLAID_ENV=production` in environment
- [ ] Use production Plaid credentials
- [ ] Enable HTTPS for all endpoints
- [ ] Implement rate limiting
- [ ] Set up monitoring and alerting
- [ ] Configure log aggregation
- [ ] Test with real bank accounts

### **Environment Variables for Production**
```env
PLAID_CLIENT_ID=your_production_client_id
PLAID_SECRET=your_production_secret
PLAID_ENV=production
FLASK_ENV=production
SECRET_KEY=your_secure_secret_key
```

## 🔗 Integration Examples

### **React Integration**
```javascript
const downloadBankData = async (publicToken) => {
  const response = await fetch('/api/one-click-download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: 'current_user_id',
      public_token: publicToken,
      days_back: 90,
      format: 'json'
    })
  });
  
  const result = await response.json();
  if (result.success) {
    // Trigger download
    const blob = new Blob([result.data]);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = result.filename;
    a.click();
  }
};
```

### **Python Script Integration**
```python
import requests

def download_user_data(user_id, public_token):
    response = requests.post('http://localhost:5000/api/one-click-download', 
        json={
            'user_id': user_id,
            'public_token': public_token,
            'days_back': 90,
            'format': 'csv'
        }
    )
    
    if response.json()['success']:
        result = response.json()
        with open(result['filename'], 'w') as f:
            f.write(result['data'])
        print(f"Downloaded {result['metadata']['transaction_count']} transactions")
```

## 📞 Support & Troubleshooting

### **Common Issues**

1. **"Missing required environment variables"**
   - Ensure `.env` file exists with `PLAID_CLIENT_ID` and `PLAID_SECRET`

2. **"Failed to create link token"**
   - Check Plaid credentials are valid
   - Verify environment (sandbox vs production)

3. **"Token exchange failed"**
   - Public token may have expired (valid for 30 minutes)
   - Ensure public token is from the same environment

4. **"No transactions found"**
   - Check date range settings
   - Verify account has transactions in the specified period

### **Debug Mode**
Enable detailed logging by setting:
```env
FLASK_DEBUG=True
PLAID_ENV=sandbox
```

## 🎯 Future Enhancements

### **Planned Features**
- [ ] **Multi-account support**: Download from multiple banks simultaneously
- [ ] **Scheduled downloads**: Automatic recurring downloads
- [ ] **Data analytics**: Built-in spending analysis and insights
- [ ] **Export to cloud**: Direct upload to Google Drive, Dropbox
- [ ] **Webhook integration**: Real-time transaction notifications
- [ ] **Mobile app**: Native iOS/Android applications

### **API Extensions**
- [ ] **Bulk user processing**: Handle multiple users in one request
- [ ] **Custom date ranges**: More flexible date selection
- [ ] **Transaction filtering**: Filter by category, amount, merchant
- [ ] **Data transformation**: Custom data mapping and enrichment

---

## 📝 License & Credits

This implementation follows Plaid's official documentation and best practices. Built with security, performance, and user experience as top priorities.

**Plaid Documentation References:**
- [Link Token Creation](https://plaid.com/docs/api/link/#linktokencreate)
- [Public Token Exchange](https://plaid.com/docs/api/items/#itempublic_tokenexchange)
- [Transactions API](https://plaid.com/docs/api/products/transactions/)
- [Security Best Practices](https://plaid.com/docs/api/security/)
