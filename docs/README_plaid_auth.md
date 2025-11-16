# Plaid Link & Token Guide

This document maps the exact steps required to turn the short-lived Plaid `link_token` into a reusable `access_token` inside this project. It supersedes the old instructions that referenced helper scripts which no longer exist.

---

## Prerequisites

- Populate `.env` with your Plaid dashboard credentials (client id, secret, and environment).
- Install dependencies and run the Flask app:

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/web/app.py
```

The web UI is served at <http://localhost:5000>.

---

## Token Flow Overview

```
1. Backend issues link_token          (BankDataPipeline.create_link_token)
2. Plaid Link runs in the browser     (helper page at /plaid-link)
3. Plaid returns public_token + item  (Plaid Link success callback)
4. Backend exchanges public_token     (/api/plaid-token → store_access_token)
5. access_token persisted for reuse   (data/plaid_access_tokens.json + ENV)
```

You can perform steps 1–4 entirely through the web helper page, or mix the CLI and UI depending on your needs.

---

## Option A — Web Helper (fastest path)

1. **Open the helper**  
   Navigate to <http://localhost:5000/plaid-link> while the Flask server is running.

2. **Request a link token**  
   - Enter a stable user id (defaults to `web_user`).  
   - Click **Request link token**.  
   - The page calls `POST /api/link-token`, which instantiates `BankDataPipeline` and returns a fresh `link-...` token.

3. **Launch Plaid Link**  
   - Click **Open Plaid Link**.  
   - The embedded Plaid Link widget launches using the link token. Use your Plaid sandbox credentials (`user_good` / `pass_good`) or production credentials depending on `PLAID_ENV`.

4. **Capture the public token**  
   - When Plaid Link completes, the helper surfaces the `public-...` token and item metadata.  
   - With **Automatically exchange public token** checked (default), the page immediately sends that token to `POST /api/plaid-token`.

5. **Access token stored & displayed**  
   - The `/api/plaid-token` endpoint exchanges the public token, persists the resulting `access-...` token to `data/plaid_access_tokens.json`, sets `PLAID_ACCESS_TOKEN`/`PLAID_ITEM_ID` in-process, and echoes the access token back to the page so you can copy it if needed.

You can now switch back to the main dashboard and click “Save token” (if you want to paste it there) or “Fetch fresh data” to pull transactions.

---

## Option B — Mixing CLI and UI

Prefer scripting? Use the `BankDataPipeline` CLI to perform the backend pieces and the helper page only for Plaid Link.

### 1. Generate a link token
```bash
python src/api/bank_data_pipeline.py --link my_user_001
```
Copy the printed `link-...` token.

### 2. Run Plaid Link
- Browse to <http://localhost:5000/plaid-link>
- Paste the link token into the “Paste an existing link token” input
- Click **Open Plaid Link** and authenticate with Plaid

### 3. Exchange the public token (CLI)
After Link finishes, the helper shows the `public-...` token. You can either let the page exchange it automatically or run:
```bash
python src/api/bank_data_pipeline.py --exchange public-sandbox-abc123...
```
The CLI prints the stored metadata and writes the access token to `data/plaid_access_tokens.json`.

---

## Where Tokens Are Saved

- File store: `data/plaid_access_tokens.json` (gitignored)
- Environment (for current process): `PLAID_ACCESS_TOKEN`, `PLAID_ITEM_ID`
- UI: both the Plaid Link helper and the main dashboard `/api/plaid-token` response include the access token for convenience

Treat these values as sensitive secrets—especially in production. Do not commit them to source control.

---

## Troubleshooting & Tips

- **“Plaid pipeline utilities are unavailable”** — ensure `requirements.txt` is installed and the server can import `src.api.bank_data_pipeline`.  
- **`PLAID_CONFIGURATION_ERROR`** — check `PLAID_CLIENT_ID`, `PLAID_SECRET`, and `PLAID_ENV` inside `.env`.  
- **“link token expired”** — generate a new token via `/api/link-token` or the CLI; they time out after ~30 minutes.  
- **Sandbox credentials** — use `user_good` / `pass_good` (and `1234` PIN if prompted).  
- **Multiple bank items** — after each successful exchange, the new token is appended to the store. You can manage them via `data/plaid_access_tokens.json` or the CLI (`--store-access`, `--download` options).  
- **Production safety** — the helper returns the raw access token for convenience because the app is assumed to run locally. If you deploy the app, remove that value from the JSON response or protect the route.

---

With the helper page and the refreshed CLI, you can now go from a Plaid link token to a stored access token in one session, making it easy to test the rest of the personal finance pipeline.*** End Patch
