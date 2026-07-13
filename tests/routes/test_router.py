import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.shared.config import settings

client = TestClient(app)

VALID_KEY = "dev-local-key"  # matches API_KEY_HASH in .env.example, see tests/shared/test_auth.py
_HEADERS = {"X-API-Key": VALID_KEY}


def _skip_if_key_mismatch():
    if settings.api_key_hash != "3700285e3c8496a57e45eb1ccd43f2424852788576961320fbb31f86f17edb61":
        pytest.skip("local .env uses a different key than the fixture assumes")


def test_list_routes_requires_api_key():
    response = client.get("/v1/routes")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"


def test_list_routes_returns_feature_collection():
    _skip_if_key_mismatch()
    response = client.get("/v1/routes", headers=_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["meta"]["total"] == 447
    assert len(body["features"]) == 50  # default page_size
    assert body["features"][0]["type"] == "Feature"


def test_list_routes_filter_matching_nothing_returns_empty_features():
    _skip_if_key_mismatch()
    response = client.get(
        "/v1/routes", headers=_HEADERS, params={"neighborhood": "Bairro Que Nao Existe"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["features"] == []
    assert body["meta"]["total"] == 0


def test_list_routes_rejects_unknown_query_param():
    _skip_if_key_mismatch()
    response = client.get("/v1/routes", headers=_HEADERS, params={"foo": "bar"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_routes_rejects_invalid_bbox():
    _skip_if_key_mismatch()
    response = client.get("/v1/routes", headers=_HEADERS, params={"bbox": "not,a,valid,bbox"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_routes_rejects_page_size_over_cap():
    _skip_if_key_mismatch()
    response = client.get("/v1/routes", headers=_HEADERS, params={"page_size": 500})
    assert response.status_code == 422


def test_get_route_by_id_returns_feature():
    _skip_if_key_mismatch()
    listed = client.get("/v1/routes", headers=_HEADERS, params={"page_size": 1}).json()
    real_id = listed["features"][0]["properties"]["id"]

    response = client.get(f"/v1/routes/{real_id}", headers=_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "Feature"
    assert body["properties"]["id"] == real_id


def test_get_route_by_id_404_for_missing_id():
    _skip_if_key_mismatch()
    response = client.get("/v1/routes/10000000", headers=_HEADERS)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
