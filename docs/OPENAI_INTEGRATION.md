# OpenAI Cloud Model Integration

## Overview
This document describes the OpenAI API integration feature that allows users to optionally use OpenAI's cloud models instead of the local Ollama instance for transaction analysis and categorization.

## Features Added

### 1. Backend Support (`src/web/llms.py`)
- Added OpenAI API client integration using the `requests` library
- New function: `_post_openai_chat()` - Handles communication with OpenAI's chat completion API
- Updated `generate_json()` to support both Ollama (default) and OpenAI
- Updated `categorize_transactions()` to accept OpenAI API key parameter
- Supports JSON mode for structured responses from OpenAI models

### 2. API Endpoints (`src/web/app.py`)
Both main endpoints now accept additional parameters:
- `openai_api_key`: User-provided OpenAI API key (optional)
- `use_openai`: Boolean flag to enable OpenAI mode (optional)

**Updated Endpoints:**
- `/api/finance-tip` - Finance tip generation
- `/api/categorize-transactions` - Transaction categorization

### 3. Frontend UI

#### Finance Tip Page (`templates/finance_tip.html`)
Added new "LLM Provider" section:
- Checkbox to enable OpenAI cloud model
- Password input field for OpenAI API key
- Informational text explaining the feature
- API key is only sent with the request, never stored on server

#### Categorize Transactions Page (`templates/categorize_transactions.html`)
Added identical "LLM Provider" section:
- Same UI components as finance tip page
- Consistent user experience across both features

## Configuration

### Environment Variables
You can set default OpenAI configuration via environment variables:

```bash
# OpenAI API Key (optional, users can provide their own via UI)
OPENAI_API_KEY=sk-your-key-here

# OpenAI Model to use (default: gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini

# OpenAI API Base URL (default: https://api.openai.com/v1)
OPENAI_BASE_URL=https://api.openai.com/v1
```

### Default Behavior
- **Without user input:** Uses local Ollama instance (existing behavior)
- **With OpenAI checkbox + API key:** Uses OpenAI's cloud models
- **With OPENAI_API_KEY env var:** Can use OpenAI without UI input

## User Workflow

1. **Navigate to Finance Tip or Categorize page**
2. **Optional: Enable OpenAI**
   - Check "Use OpenAI Cloud Model" checkbox
   - Enter OpenAI API key (starts with `sk-`)
3. **Upload CSV or fetch transactions** (as before)
4. **Click Generate/Categorize button**

The system will automatically route to OpenAI if enabled, otherwise uses Ollama.

## Security Considerations

- ✅ API keys are sent via POST request body (not URL)
- ✅ API keys are NOT logged or stored on the server
- ✅ Password input field masks the API key in the UI
- ✅ API key is only kept in browser memory during the session
- ⚠️ Users should use API keys with appropriate rate limits and budgets
- ⚠️ Consider implementing API key validation before processing

## Model Comparison

| Feature | Ollama (Default) | OpenAI Cloud |
|---------|------------------|--------------|
| **Cost** | Free (local compute) | Pay per token |
| **Speed** | Depends on local hardware | Generally fast |
| **Privacy** | 100% local | Data sent to OpenAI |
| **Setup** | Requires Ollama installation | Just need API key |
| **Quality** | Varies by model | Consistently high (GPT-4o) |
| **Offline** | Yes | No |

## Example API Request

### With OpenAI
```json
POST /api/finance-tip
{
  "fetch_fresh": false,
  "lookback_days": 90,
  "use_openai": true,
  "openai_api_key": "sk-your-key-here"
}
```

### With CSV Upload + OpenAI
```json
POST /api/categorize-transactions
{
  "use_csv": true,
  "csv_data": "date,name,amount\n2025-01-01,Store,50.00",
  "lookback_days": 90,
  "use_openai": true,
  "openai_api_key": "sk-your-key-here"
}
```

## Error Handling

The system handles various error scenarios:
- Missing API key when OpenAI is enabled
- Invalid API key format
- Network errors connecting to OpenAI
- Rate limit errors from OpenAI
- Invalid JSON responses

All errors are returned to the user with descriptive messages.

## Future Enhancements

Potential improvements for this feature:
1. Support for other cloud providers (Anthropic Claude, Azure OpenAI)
2. API key validation endpoint
3. Model selection dropdown (GPT-3.5, GPT-4, GPT-4o)
4. Cost estimation before processing
5. Response caching to reduce API calls
6. Server-side API key storage (encrypted) for convenience
7. Usage tracking and analytics

## Testing

To test the OpenAI integration:

1. **Get an OpenAI API key** from https://platform.openai.com/api-keys
2. **Start the Flask app:** `python src/web/app.py`
3. **Navigate to** http://localhost:5000
4. **Check "Use OpenAI Cloud Model"**
5. **Enter your API key**
6. **Upload CSV or use existing data**
7. **Click Generate Tip or Categorize**

## Troubleshooting

### "OpenAI API key is required" error
- Ensure the checkbox is checked AND the API key is entered
- Verify the API key starts with `sk-`

### Network errors
- Check internet connectivity
- Verify OpenAI API status: https://status.openai.com
- Check if API key has appropriate permissions

### Timeout errors
- OpenAI requests have 120-second timeout
- Large transaction sets may take longer
- Consider reducing lookback days

## Code Files Modified

1. `src/web/llms.py` - Core LLM integration logic
2. `src/web/app.py` - Flask route handlers
3. `src/web/templates/finance_tip.html` - UI for finance tips
4. `src/web/templates/categorize_transactions.html` - UI for categorization

## Dependencies

No new Python dependencies required! Uses existing `requests` library.

```python
# Already in requirements.txt
requests>=2.31.0
```

