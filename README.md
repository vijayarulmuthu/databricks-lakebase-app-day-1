# Massive + Lakebase Databricks App

A Databricks App that:
- Connects to **Lakebase** (Databricks-managed Postgres) using a single `LAKEBASE_URL` secret (a native Postgres role with a static password)
- Calls the **Massive API** (financial market data) using a key stored in a Databricks secret scope
- Syncs Massive API data into Lakebase in batches
- Serves a stock **watchlist web UI**: add/remove tickers, view live OHLCV prices, a cached company profile + 30-day sparkline, and on-demand news headlines, all personalized per logged-in user
- Caches per-symbol data (company profile, price history, news) in Lakebase and shares it across users to minimize Massive API calls

## Files

- `app.py` - Flask app serving both the generic sync API and the watchlist UI/API (see [Endpoints](#endpoints))
- `lakebase.py` - Lakebase connection helper (single `LAKEBASE_URL`, psycopg2 + SQLAlchemy)
- `massive_client.py` - Massive API client: paginated bulk sync plus single-call helpers for price, ticker details, price history, and news
- `templates/index.html` - Single-page watchlist UI (vanilla JS, no build step) - add/remove tickers, sparklines, price-change badges, and an expandable news panel per row
- `setup_secrets.py` - One-time script to create the secret scopes and store the Massive API key + Lakebase URL
- `app.yaml` - Databricks App deployment config (command + env vars)
- `.env.example` - Local dev env var template (copy to `.env`, do not commit real values)

## Step-by-step setup

### 1. Create a Massive.com account and get an API key

1. Go to [https://massive.com](https://massive.com) and sign up for a new account (or log in if you already have one).
2. Once logged in, open your account/workspace **Settings** (or **Developer** / **API** section, depending on Massive's current UI).
3. Find **API Keys** and click **Create API Key** (or **Generate New Key**).
4. Give the key a name (e.g. `databricks-app`) and copy the generated key value immediately — most providers only show it once.
5. Keep this key handy for step 3 (Store your secrets) below. Do **not** put it in code, `.env` committed to git, or anywhere else in plaintext.

> If Massive's console differs from the steps above, look for **API Keys**, **Tokens**, or **Credentials** under your account/organization settings — the key is what authenticates requests to `https://api.massive.com` in `massive_client.py`.

### 2. Create a Lakebase instance and a native-password role

1. In your Databricks workspace, go to **Catalog** (left sidebar) and select the **Lakebase** tab (or search "Lakebase" in the workspace search bar).
2. Click **Create Lakebase instance** (sometimes labeled **Create database instance**).
   - Give it a name (e.g. `massive-sync-db`).
   - Choose the capacity/compute size and region appropriate for your workload (defaults are fine to start).
   - Click **Create** and wait for the instance to reach the **Available**/**Running** state.
3. Open the newly created instance, then go to the **Roles & Databases** tab (sometimes called **Permissions** or **Roles**).
4. **Enable native (password) authentication** for the instance if it isn't already on:
   - Look for an authentication setting such as **Native passwords** or **Password authentication** and toggle/enable it. By default some Lakebase instances only support OAuth/token-based auth — you need password auth enabled so the role below gets a static password instead of a short-lived token.
5. **Create a new role**:
   - Click **Add role** / **Create role**.
   - Choose **Password** as the authentication method (not OAuth).
   - Name the role (e.g. `massive_app`) and let Databricks generate (or set) a password.
6. **Copy the connection URL** shown for the role. It will look like:

   ```
   postgresql://<role>:<password>@<host>.database.cloud.databricks.com:5432/databricks_postgres?sslmode=require
   ```

   Keep this URL — you'll paste it into `setup_secrets.py`'s prompt in the next step.

### 3. Store your secrets

Run once from a **Databricks notebook** in your workspace (no CLI needed):

1. Create a new notebook (or open the Git folder you'll create in step 5, once it's cloned) and attach it to any running cluster.
2. In a cell, run:

   ```python
   %sh python setup_secrets.py
   ```

   or open a terminal from the notebook (**Run** > **Open terminal**, if enabled on your cluster) and run `python setup_secrets.py` there.

This prompts (via `getpass`, so nothing is echoed or written to disk/shell history) for:
- Your **Massive API key** (from step 1) → stored as secret `massive/api-key`
- Your **Lakebase connection URL** (from step 2) → stored as secret `database/lakebase-url`

### 4. Configure environment variables (local dev)

Copy `.env.example` to `.env` and paste your Lakebase URL as `LAKEBASE_URL` for local runs:

```bash
cp .env.example .env
```

For deployment, `app.yaml` already pulls `LAKEBASE_URL` from the `database/lakebase-url` secret automatically — no manual editing needed there.

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Run locally

```bash
python app.py
```

### 7. Create a Git folder in Databricks and deploy the app (no CLI required)

All of this is done through the Databricks workspace UI:

1. **Create a Git folder**:
   - In the Databricks workspace sidebar, click **Workspace** > **Create** > **Git folder** (in older UIs this is called **Repos** > **Add Repo**).
   - Paste the Git URL of this project's repository (e.g. your GitHub/GitLab remote for this codebase).
   - Choose a folder name and click **Create Git folder**. Databricks will clone the repo directly into your workspace — this becomes the source for your app.

2. **Create the Databricks App**:
   - In the sidebar, go to **Compute** > **Apps** (or search "Apps" in the workspace search bar).
   - Click **Create app**, then choose **Custom** (or "From scratch").
   - Give the app a name (e.g. `massive-lakebase-sync`).

3. **Point the app at your Git folder**:
   - When prompted for the source code location, select **Workspace files** / **Git folder** and browse to the Git folder you created in step 1 (the folder containing `app.py` and `app.yaml`).
   - Databricks will read `app.yaml` from that folder automatically to configure the `command` and `env` (including the `LAKEBASE_URL`, `MASSIVE_API_BASE_URL`, and secret scope/key references).

4. **Deploy**:
   - Click **Deploy** (or **Create and deploy**) in the Apps UI. Databricks will build and start the app using the Git folder's current contents — no `databricks` CLI commands are needed.
   - Whenever you update the code, pull the latest changes into the Git folder (**Git folder** > **Pull**, via the UI) and click **Deploy** again in the Apps UI to redeploy.

5. Once deployed, open the app's URL from the Apps UI and hit `GET /healthz` to confirm it's running, then try `POST /sync` to pull data from Massive into Lakebase.

## Endpoints

- `GET /healthz` - health check
- `GET /records?limit=100` - read synced records from Lakebase
- `POST /sync?batch_size=500` with optional JSON body `{"path": "/records"}` - pull from Massive API and upsert into Lakebase
- `GET /watchlist` - get the current user's watchlist with full OHLCV, plus each symbol's cached company profile and 30-day price history
- `POST /watchlist` with JSON/form body `{"symbol": "AAPL"}` - fetch the latest OHLCV bar for a symbol (one Massive API call), refresh its cached profile/price history if stale, and add/update it on the current user's watchlist
- `DELETE /watchlist/<symbol>` - remove a symbol from the current user's watchlist
- `GET /watchlist/<symbol>/news` - fetch (and cache) recent news headlines for a symbol already on the current user's watchlist

The current user is resolved from the `X-Forwarded-Email` header that Databricks Apps injects for the logged-in user, falling back to the Databricks SDK's current-user API for local development.

### Per-symbol caching

Two tables cache Massive API responses **per symbol** (not per user), so adding the same symbol from multiple users' watchlists doesn't multiply API calls:

- `ticker_details` - company profile + 30-day price history, refreshed at most every `TICKER_DETAILS_MAX_AGE_HOURS` (default 24h)
- `ticker_news` - news headlines, refreshed at most every `TICKER_NEWS_MAX_AGE_HOURS` (default 6h), fetched only when a user opens the "News" panel for a symbol

## Enabling Change Data Feed (CDF) for Postgres tables

Lakebase supports **Change Data Feed (CDF)**, a managed way to stream row-level inserts/updates/deletes
from your Lakebase Postgres tables into Unity Catalog Delta tables (no Debezium, no custom connectors).
CDF is enabled per-**schema** in the `databricks_postgres` database, and every table in that schema that
meets two conditions is picked up automatically: it has `REPLICA IDENTITY FULL` set, and it has at least
one row.

### 1. Set `REPLICA IDENTITY FULL` on the tables you want to track

By default, Postgres only logs primary-key columns on change. To capture full row contents (needed for
CDF), enable `REPLICA IDENTITY FULL` on each table — including `watchlist`, `massive_records`,
`ticker_details`, and `ticker_news` from this app:

```sql
ALTER TABLE watchlist REPLICA IDENTITY FULL;
ALTER TABLE massive_records REPLICA IDENTITY FULL;
ALTER TABLE ticker_details REPLICA IDENTITY FULL;
ALTER TABLE ticker_news REPLICA IDENTITY FULL;
```

Run this once per table, either from a Databricks SQL editor connected to your Lakebase instance, or
from a `psql` session using your `LAKEBASE_URL`. Any new table you add later (e.g. via `ensure_table`-style
helpers in `app.py`) needs the same `ALTER TABLE ... REPLICA IDENTITY FULL` statement run once before it
will be included in the feed. Tables with the setting but zero rows are skipped until the first row is
inserted, then picked up automatically.

You can confirm which tables currently qualify by querying:

```sql
SELECT * FROM wal2delta.tables;
```

### 2. Start CDF from the Lakebase UI

1. In your Databricks workspace, open the **Lakebase** tab for your instance.
2. Go to **Lakebase CDF** and click **Start**.
3. Select the `databricks_postgres` database and the schema containing your tables (the default
   schema, `public`, works — it's inside `databricks_postgres`).
4. Choose the Unity Catalog destination schema/catalog where the CDF history tables should land.
5. Confirm — the UI shows a preview of qualifying tables (e.g. `watchlist`, `massive_records`) and
   their sync status before you start.

Once running, each qualifying table gets a corresponding Delta table named `lb_<table_name>_history`
(e.g. `lb_watchlist_history`) in Unity Catalog, updated roughly every 15 seconds. Each row includes
metadata columns (`_pg_change_type`, `_pg_lsn`, `_pg_xid`, `_timestamp`, `_sort_by`) describing the
change, so downstream Delta Live Tables/pipelines can build Silver/Gold layers off the append-only
history.

> **Note:** Disabling CDF is lossy — changes made while it's off aren't captured, and re-enabling
> triggers a full resync (every row reloaded as an `insert`). There's no per-table exclusion option
> within an enabled schema; the only way to keep a table out of the feed is to not set
> `REPLICA IDENTITY FULL` on it.

## Notes

- Lakebase auth uses a single `LAKEBASE_URL` secret pointing at a native Postgres role with a
  static, non-expiring password — no token refresh logic needed in `lakebase.py`.
- The Massive API pagination in `massive_client.py` assumes a `{"items": [...], "next_cursor": ...}`
  cursor-based shape. Adjust `paginated_get` to match the real API's pagination contract.
- For very large batch upserts, consider `psycopg2.extras.execute_values` instead of per-row inserts.
