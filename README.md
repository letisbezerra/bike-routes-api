# bike-routes-api

[![CI](https://github.com/letisbezerra/bike-routes-api/actions/workflows/ci.yml/badge.svg)](https://github.com/letisbezerra/bike-routes-api/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue)](pyproject.toml)

Free, public REST API over Fortaleza's (Ceará, Brazil) open bike infrastructure data — bike routes, parking, bike-share stations, and rest points.

Fortaleza's city hall publishes this data as raw GeoJSON files on its open-data portal, but offers no API to query it — anyone who wants to build on top of it has to download the full files and parse them client-side, with no filtering, no pagination, and no spatial queries. This project turns that into a proper, versioned, authenticated REST API: pick a bounding box, filter by category, paginate — get back GeoJSON `Feature`s any map library can render directly.

**Fonte: AMC/Prefeitura de Fortaleza.** Data published by the city under its "Dados Abertos" portal with no declared license — used here with attribution and no implied endorsement by the city.

## Data

| Resource | Endpoint | Geometry |
|---|---|---|
| Bike routes (ciclovias/ciclofaixas/ciclorrotas) | `/v1/routes` | LineString |
| Bike parking (paraciclos/bicicletários) | `/v1/parking` | Point |
| Bike-share stations (Bicicletar) | `/v1/stations` | Point |
| Rest points | `/v1/rest-points` | Point |
| Leisure bike routes | `/v1/leisure-routes` | MultiLineString |

Every resource supports pagination and a bounding-box filter (`bbox=min_lon,min_lat,max_lon,max_lat`); some support additional filters — see the interactive docs.

## Authentication

Every request requires an `X-API-Key` header. Keys are issued manually (no self-service signup yet) — see [Local setup](#local-setup) to issue your own for development, or contact the maintainer for a production key.

## API docs

Interactive Swagger UI: `/docs` (also `/redoc`) on any running instance. Public on every environment — the API is public/open-data, auth and rate limiting are the actual protection, not hiding the docs.

## Local setup

Requires [`uv`](https://docs.astral.sh/uv/) and Docker.

```bash
git clone https://github.com/letisbezerra/bike-routes-api.git
cd bike-routes-api
cp .env.example .env

docker compose up -d              # local PostGIS
uv sync --all-groups

uv run alembic upgrade head       # create schema
uv run python -m scripts.ingest   # load data/raw/*.geojson into PostGIS

uv run python -m scripts.manage_keys issue --label "local-dev"
# copy the printed key — shown once

uv run uvicorn app.main:app --reload
```

Then, with the key from above:

```bash
curl -H "X-API-Key: <your-key>" "http://127.0.0.1:8000/v1/routes?page_size=5"
curl -H "X-API-Key: <your-key>" "http://127.0.0.1:8000/v1/routes/1"
```

## Running tests

```bash
docker compose up -d
uv run pytest
```

## Managing API keys

```bash
uv run python -m scripts.manage_keys issue --label "who this is for"
uv run python -m scripts.manage_keys list
uv run python -m scripts.manage_keys revoke --key-id <id>
```

## Architecture

Full stack decisions and reasoning: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Data quality notes and license detail: [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## Contributing

External contributions require a signed CLA — see [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a PR.

## License

Code: AGPL-3.0 — see [`LICENSE`](LICENSE). If you can't accept AGPL's obligations (e.g. running a modified version as a network service without publishing the modified source), a commercial license is planned — see [`COMMERCIAL-LICENSE.md`](COMMERCIAL-LICENSE.md).

Data: no license declared by the source portal — used with mandatory attribution ("Fonte: AMC/Prefeitura de Fortaleza"), see [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) for full reasoning.
