# Bloc Sales CRM

A Sales CRM with smart, transactional lead assignment from Google Sheets into a FastAPI + Postgres backend with a real-time React dashboard.

## Running the stack

1. Copy env templates:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

2. Start via Docker Compose from the repo root:

```bash
docker compose -f infra/docker-compose.yml up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

## Google Sheets automation

Configure n8n / Zapier / Make with this flow:

- **Trigger**: "New row in Google Sheet" on your leads sheet.
- **Transform**: Map columns to a JSON body:
  - `name`
  - `phone`
  - `timestamp`
  - `lead_source`
  - `city`
  - `state`
  - `metadata` (optional JSON blob)
- **Action**: `POST` the JSON to:

```text
POST $BACKEND_URL/api/leads/webhook
Header: X-Webhook-Secret: <value from backend .env>
Content-Type: application/json
```

The backend enforces idempotency using `(phone, timestamp)` unique constraint and will safely handle retries.

## Security & non-functional notes

- Webhook is protected by the `X-Webhook-Secret` header and `WEBHOOK_SECRET` env var.
- DB credentials and secrets are provided via env vars / `.env` files, never hard-coded.
- All assignment logic runs inside a single DB transaction to avoid race conditions.
- Round Robin fairness and daily caps are enforced by the `rr_pointers` and `caller_daily_counters` tables.

## Minimal tests

You can add fast backend tests using `pytest` (not installed by default):

- Exercise the assignment engine with multiple callers and leads to verify:
  - state-based routing and global fallback
  - daily caps and unassigned queue behaviour
  - duplicate webhook payloads return the same logical lead

