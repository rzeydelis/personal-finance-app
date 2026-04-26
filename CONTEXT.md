# Personal Finance App Context

## What this project is
This is a Flask-based personal finance web app that analyzes transaction history from:
- CSV uploads
- Plaid transaction pulls

It also includes Apple Health and Apple Watch analysis endpoints, plus deployment assets for running behind Gunicorn + Nginx on Ubuntu/EC2.

Primary entrypoint:
- `src/web/app.py`

## Core capabilities
- Generate one actionable finance tip from recent transactions (`/api/finance-tip`)
- Monthly spend breakdown with category + subscription detection (`/api/monthly-spend`)
- Plaid token handling + transaction fetch support (`/api/plaid-token`, `/api/link-token`)
- Apple Health XML parsing + analysis (`/api/apple-health/analyze`)
- Apple Watch heart-rate parsing from XML and JSON payloads
  - `/api/apple-watch/heart-rate`
  - `/api/apple-watch/healthkit-sync`
- Basic email waitlist capture (`/api/email-signup`)

## Tech stack
- Python 3.8+
- Flask 2.3
- Gunicorn (production WSGI server)
- Plaid Python SDK
- Requests for LLM HTTP calls
- Optional OpenAI/Ollama model usage
- DefusedXML for Apple Health XML parsing safety
- Pytest for tests

## Repository map (high-value files)
- `src/web/app.py`: main Flask app, routing, API security, response headers
- `src/web/llms.py`: Ollama/OpenAI request logic and JSON parsing
- `src/web/finance_tip.py`: finance tip prompt + result shaping
- `src/web/transaction_insights.py`: summary/aggregation helpers
- `src/web/subscription_finder.py`: recurring subscription heuristics
- `src/web/apple_health_analysis.py`: LLM-based analysis of parsed health data
- `src/web/utils.py`: CSV parser for transaction uploads
- `src/api/get_bank_trx.py`: Plaid credential/token/transaction utilities
- `src/api/bank_data_pipeline.py`: higher-level Plaid workflow orchestration
- `src/api/apple_health_parser.py`: Apple Health and Apple Watch parsers
- `tests/test_parsing.py`: transaction parsing and summary tests
- `tests/test_apple_health.py`: Apple Health/Watch parser tests and page smoke tests
- `docs/README.md`, `QUICKSTART.md`: user/dev docs
- `deploy/systemd/personal-finance-app.service`: systemd unit
- `deploy/nginx/personal-finance-app.conf`: Nginx reverse proxy config
- `scripts/ec2/bootstrap_ubuntu.sh`: EC2 bootstrap script

## Runtime behavior overview
1. Client submits CSV or requests Plaid-backed data.
2. App normalizes transaction records into a shared structure (`date`, `datetime`, `merchant/name`, `amount`, etc.).
3. Endpoints run:
- rule-based summaries (`transaction_insights.py`)
- optional LLM categorization/tips (`llms.py`)
- optional subscription heuristics (`subscription_finder.py`)
4. API returns JSON payloads used by templates/pages.

For Apple Health:
1. XML (or HealthKit-style JSON) is parsed in `src/api/apple_health_parser.py`.
2. Aggregated metrics are returned directly and can optionally be passed to LLM analysis.

## Local development
Create environment + install:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r dev-requirements.txt
```

Run app:
```bash
python src/web/app.py
```

Default local URL:
- `http://localhost:5000`

Useful pages:
- `/tip` (also `/`)
- `/monthly-spend`
- `/health`
- `/apple-watch`
- `/plaid-link`
- `/healthz`

## API auth + security model
Protected API paths include:
- `/api/plaid-token`
- `/api/link-token`
- `/api/finance-tip`
- `/api/monthly-spend`
- `/api/apple-health/analyze`
- `/api/apple-watch/heart-rate`
- `/api/apple-watch/healthkit-sync`

Auth behavior:
- If `APP_API_TOKEN` is set: protected APIs require token via `Authorization: Bearer ...`, `X-API-Key`, or request body.
- If not set: protected APIs are loopback-only (local host/local IP, no forwarded proxy header).

Other controls:
- request rate limit (`API_RATE_LIMIT_WINDOW_SECONDS`, `API_RATE_LIMIT_MAX_REQUESTS`)
- JSON body size limit (`MAX_JSON_BODY_BYTES`)
- upload cap 350 MB (`MAX_CONTENT_LENGTH`)
- response security headers + CSP in `app.py`

## Environment variables (important)
App/API:
- `APP_API_TOKEN`
- `MAX_JSON_BODY_BYTES`
- `API_RATE_LIMIT_WINDOW_SECONDS`
- `API_RATE_LIMIT_MAX_REQUESTS`
- `FLASK_DEBUG`

Plaid:
- `PLAID_CLIENT_ID`
- `PLAID_SECRET`
- `PLAID_ENV` (`sandbox`, `development`, `production`)
- `PLAID_ACCESS_TOKEN`
- `PLAID_ITEM_ID`
- `PLAID_PUBLIC_TOKEN`
- optional account filters: `PLAID_ACCOUNT_NAME_FILTER`, `PLAID_ACCOUNT_IDS`, `PLAID_ACCOUNT_SUBTYPES`

LLM:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `OLLAMA_TIMEOUT_SECONDS`

## Data and persistence
- Transaction exports: `data/transactions_<start>_to_<end>.txt`
- Plaid token cache: `data/plaid_access_tokens.json` (sensitive; gitignored)
- Email waitlist storage: `src/web/email_signups.json`

## Tests
Run:
```bash
pytest
```

Current test focus:
- Transaction text parsing and spend summary behavior
- Apple Health + Apple Watch parsing logic
- Basic page rendering checks for `/health` and `/apple-watch`

## Deployment notes
Expected production topology:
- Gunicorn bound to `127.0.0.1:8000`
- Nginx reverse proxy on `:80`
- systemd service `personal-finance-app`

Bootstrap script:
- `scripts/ec2/bootstrap_ubuntu.sh`

Related docs:
- `docs/DEPLOY_EC2.md`
- `deploy/systemd/personal-finance-app.service`
- `deploy/nginx/personal-finance-app.conf`
- `docs/designs/pluto-finance-agentic-architecture.md` (future TODO plan)

## Known caveats (current state)
- `scripts/ec2/bootstrap_ubuntu.sh` references `deploy/env/personal-finance-app.env.example`, but that file is not present in `deploy/`.
- Some docs reference files like `sample_transactions.csv`/extra docs that are not currently visible in the repository root.
- `tests/test_parsing.py` references an `add_web_to_syspath` fixture; ensure your local pytest setup provides it (or add `tests/conftest.py` if needed).

