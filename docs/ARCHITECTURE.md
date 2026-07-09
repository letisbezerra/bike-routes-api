# Architecture — bike-routes-api

Decisions and their reasoning.

## Stack

- **Framework: FastAPI.** Beats Django/GeoDjango on performance and free OpenAPI docs; beats Flask on both counts too plus built-in validation. Django's edge (GeoDjango's native spatial ORM, admin panel for data curation) doesn't outweigh pulling in auth/sessions/admin machinery this public GET-only API doesn't use — data curation is solved by a clean ingestion script instead.
- **Database: PostgreSQL + PostGIS, via GeoAlchemy2.** Rejected SQLite/SpatiaLite (free app hosts have ephemeral disk — would risk data loss; weaker query planner for complex spatial predicates), Firebase/Firestore (no native LineString/spatial index — can't represent bike routes correctly), MongoDB (data is tabular, not schema-flexible), DuckDB (analytical tool, not built for concurrent request serving). Free hosting: Supabase or Neon (managed Postgres, free tier, PostGIS included, persistent).

## Components

```
Prefeitura (CKAN) → scripts/ingest.py (manual trigger) → PostGIS
                                                              ↑
                                     FastAPI (routers/services/repositories)
                                     rate limiting: slowapi (in-process middleware)
                                                              ↑
                                                          Clients
```

- **Ingestion is a separate script, not part of the live API.** Runs on demand (city data changes rarely). Writes straight to PostGIS; the API never touches raw GeoJSON or loads GeoPandas/Fiona at runtime. Scheduling it (GitHub Actions `schedule`, free on public repos) is deferred until there's an actual need — not built now.
- **No cache layer (Redis) for MVP.** ~1000 rows with a GiST index answers in milliseconds; adding Redis now would be solving a problem we don't have. Revisit if real traffic shows a need.
- **Rate limiting lives in the API process** (`slowapi` middleware), not a separate reverse proxy — simplest option that needs no extra infra.
- Scalability is designed in via the choices themselves (PostGIS, stateless API, proper indexing), not via extra moving parts deployed ahead of need — YAGNI, not under-engineering.

## Data model

One table per feature type (mixed geometries across source layers rule out one generic table). Field names: English `snake_case` (broader dev audience); data content (bairro names, categories) stays Portuguese.

| Table | Geometry | Key fields |
|---|---|---|
| `bike_routes` | LineString | name, category (enum), length_km, segment, road_position, direction, pavement, separation_element, implemented_at, neighborhoods, reference_year, source_id |
| `bike_parking` | Point | name, spot_count, type (enum), operating_hours |
| `bike_share_stations` | Point | name, neighborhood, regional, inaugurated_at, status (enum, normalized), sponsor, current_slots, station_type, source_id |
| `rest_points` | Point | name, image_url (extracted from source HTML, sanitized) |
| `leisure_routes` | MultiLineString | name, support_count |

- **ID**: generated at ingestion (own primary key), never trusts source `Id`/`ID` (has gaps). Original kept as `source_id` for traceability — and used as the upsert key so ids stay stable across re-ingestion, since this API is meant to be built on top of (external references to an id shouldn't silently break on a data refresh).
- **Raw data**: not duplicated in its own table — CKAN is the source of truth/history; re-ingest instead of storing an audit copy.
- **Enum vs free text**: fields used as API filters (`category`, `type`, `status`) are constrained enums; descriptive fields (`name`, `segment`) stay free text.
- **Indexes**: GiST on every geometry column; b-tree on `category`/`neighborhood` (likely filter candidates).
- **Layering**: routers → services → repositories (pragmatic separation, not full Clean Architecture — no business-logic complexity here to justify entity/use-case/port abstraction layers).
- **Paradigm**: pragmatic OOP, not heavy OOP. Classes where state is encapsulated (ORM models, Pydantic schemas, `service`/`repository` holding an injected DB session) — no inheritance chains or abstract base classes without a concrete need. Route handlers stay plain functions (`@router.get(...)`), FastAPI's idiomatic style, not class-based views.

## Folder structure

Modular by domain, not by technical layer — 5 largely independent resources, each self-contained (matches FastAPI's own "Bigger Applications" guidance):

```
app/
├── routes/        # bike_routes: router, service, repository, models, schemas
├── parking/       # bike_parking
├── stations/      # bike_share_stations
├── rest_points/   # rest_points
├── leisure_routes/ # leisure_routes
├── shared/        # db session, config, middleware, auth, rate limiting
└── main.py
tests/             # mirrors app/ by domain — tests/routes/, tests/parking/, ...
data/
└── raw/           # source GeoJSON snapshots (committed — keeps the project runnable without hitting CKAN first)
scripts/
└── ingest.py      # created when we build the ingestion pipeline
.github/
└── workflows/
    └── ci.yml     # pytest on push/PR
docker-compose.yml # local PostGIS, test-only
pyproject.toml
.env.example
LICENSE            # MIT — code license, distinct from the data attribution requirement (docs/CONTEXT.md §3)
```

## API design standards

Applies directly:
- Nouns in URLs, not verbs (`GET /routes`, not `/getRoutes`)
- Correct HTTP status codes (200/201/204/400/401/403/404/409/422/500)
- Standardized response envelope (success and error shapes)
- Strict input validation on every query param
- Pagination on every list endpoint
- Filters (`neighborhood`, `category`, bounding box) and versioning (`/v1`)
- `GET /health` — unauthenticated, unrated liveness check (needed for free-tier hosts that spin down on inactivity)
- Auto-generated OpenAPI docs
- Consistent error shape (`{"error": {"code": ..., "message": ...}}`)
- Layered structure (routers/services/repositories/models/schemas), no logic in endpoints
- Automated tests (unit + integration)
- One naming convention for all fields (`snake_case`) — the raw source files mix conventions, the API schema doesn't

Adapted for this project (no user accounts):
- Auth = API key for rate limiting, not JWT/OAuth2 user identity
- No ownership-based authorization (no resource has an "owner")
- Observability starts as structured logs; add Prometheus/Grafana only if scale demands it

Doesn't apply for MVP:
- Idempotency concerns (GET-only, inherently idempotent)
- `PUT`/`PATCH`/`DELETE` (data is city-hall-sourced, not user-editable)

## Security

Priority stays correctness → security (not reordered) — most real vulnerabilities are correctness bugs (bad input handling, broken validation), so building correct logic already does most of the security work. Given this is a public API from day one, hardening isn't premature — unlike Redis/cron, abuse risk isn't hypothetical.

**API key: mandatory for every request**, not optional. Gives per-key traceability and revocation, not just weak/spoofable IP tracking — worth the signup friction, standard for serious public data APIs.

**CORS: open (`*`), not restrictive.** Reversed from the earlier draft — CORS only affects browser JS callers; it does nothing against server-side/curl/script abuse, which rate limiting + mandatory keys already cover. Restricting it would only block legitimate developers building web frontends, contradicting the project's own goal (usable from web, mobile, anywhere).

For API consumers:
- Rate limiting by IP **and** mandatory API key, with temporary ban after repeated violations
- Strict validation on all input (bbox, pagination, filters) — Pydantic `extra="forbid"` rejects unexpected params; capped page size and bbox area block expensive/malicious queries
- HTTPS enforced, redirect HTTP→HTTPS, HSTS header (`includeSubDomains`)
- Security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
- CORS open (`*`) — see above
- Errors never leak internals (stack trace, file paths, raw SQL errors) — generic message to client, full detail server-side only
- `Imagem` field (raw HTML in source data) sanitized or dropped at ingestion — known stored-XSS risk
- OpenAPI docs (`/docs`, `/redoc`) stay public on purpose — documentation is part of the product, not a leak
- Cloudflare (free tier) in front of the API — DDoS/bot mitigation, zero code

For the operator (me):
- DB credentials and API keys via env vars/secrets manager, never hardcoded
- DB app user has least privilege (`SELECT` only), never superuser
- Database not publicly network-exposed, only the app reaches it
- API keys stored hashed (one-way, like a password), never plaintext or reversibly encrypted; revocable without redeploying
- Encryption at rest and TLS on the DB connection: provided by Supabase/Neon by default, not something we implement
- Dependency vulnerability scanning (`pip-audit`/Dependabot) + pinned/locked versions, not just scanning on the fly
- Logs aimed at detecting abuse/attack, not just performance

## Testing

- **Framework**: `pytest` + FastAPI's `TestClient`.
- **Two layers**: unit (`service`/`repository` isolated, DB mocked — pure logic) and integration/contract (`TestClient` hitting real endpoints against a real test PostGIS — spatial queries can't be meaningfully tested any other way, per the earlier SQLite/Firebase rejection).
- **Test database: real PostGIS via local Docker Compose** (ephemeral container, test-only — new tool, not used in production).
- **Structure**: `tests/` mirrors `app/` by domain (`tests/routes/`, `tests/parking/`, ...).
- **Goal**: solid coverage of business logic and routes, not a 100% number chase.
