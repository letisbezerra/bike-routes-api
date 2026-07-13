---
name: verify
description: Build/launch/drive recipe for verifying bike-routes-api changes at runtime.
---

# Verifying bike-routes-api

## Launch

```bash
docker compose up -d              # local PostGIS on :5433, wait for "healthy"
lsof -ti:8000 | xargs kill -9 2>/dev/null   # kill any stale uvicorn first
uv run uvicorn app.main:app --port 8000 &
```

`/health` responding 200 confirms the app is up (works even before Docker
finishes, but real resource endpoints need the DB).

## Drive

All resource endpoints require `X-API-Key: dev-local-key` (matches
`API_KEY_HASH` in `.env.example` — if local `.env` uses a different key,
generate the hash: `python3 -c "import hashlib; print(hashlib.sha256(b'your-key').hexdigest())"`).

```bash
curl -H "X-API-Key: dev-local-key" "http://127.0.0.1:8000/v1/routes"
curl -H "X-API-Key: dev-local-key" "http://127.0.0.1:8000/v1/routes/1"
```

Resources: `routes`, `parking`, `stations`, `rest-points`, `leisure-routes`.
Swagger UI at `http://127.0.0.1:8000/docs` (has a working "Authorize" button).

## Gotchas

- Rate limit is a single shared bucket per client across every endpoint
  (`@limiter.shared_limit(default_limit, api_scope)`, `app/shared/middleware.py`)
  — exhausting it on one endpoint blocks all the others too. `/health` is the
  one exception, intentionally undecorated. To test 429 without waiting,
  override the limit: `RATE_LIMIT_PER_MINUTE=3 uv run uvicorn app.main:app --port 8000`.
- Docker Desktop needs to be open before `docker compose up -d` — if the
  daemon isn't running you get "Cannot connect to the Docker daemon", not
  an obvious hint to start Docker Desktop.
- Filter values are lowercase enum strings (e.g. `?type=bicicletario`, not
  `BICICLETARIO`) — check `app/<resource>/models.py` for exact enum values.
- Always `lsof -ti:8000 | xargs kill -9` before relaunching — a stale
  process from a previous run silently keeps serving old code on the same
  port.
