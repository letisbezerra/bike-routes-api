from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_parking_returns_feature_collection(api_headers):
    response = client.get("/v1/parking", headers=api_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["meta"]["total"] == 301
    assert len(body["features"]) == 50  # default page_size
    assert body["features"][0]["type"] == "Feature"


def test_list_parking_filter_matching_nothing_returns_empty_features(api_headers):
    response = client.get(
        "/v1/parking", headers=api_headers, params={"type": "bicicletario", "page_size": 5}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 5
    assert all(f["properties"]["type"] == "bicicletario" for f in body["features"])


def test_get_parking_by_id_returns_feature(api_headers):
    listed = client.get("/v1/parking", headers=api_headers, params={"page_size": 1}).json()
    real_id = listed["features"][0]["properties"]["id"]

    response = client.get(f"/v1/parking/{real_id}", headers=api_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "Feature"
    assert body["properties"]["id"] == real_id


def test_get_parking_by_id_404_for_missing_id(api_headers):
    response = client.get("/v1/parking/10000000", headers=api_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_list_parking_always_reports_clipped_false(api_headers):
    """bike_parking is Point geometry — the shared Feature.clipped field
    (docs/specs/06-geometry-clipping.md) never applies here, bbox or not."""
    response = client.get(
        "/v1/parking",
        headers=api_headers,
        params={"page_size": 5, "bbox": "-38.64,-3.89,-38.41,-3.68"},
    )
    body = response.json()
    assert len(body["features"]) == 5
    assert all(feature["clipped"] is False for feature in body["features"])
