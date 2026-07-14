from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_stations_returns_feature_collection(api_headers):
    response = client.get("/v1/stations", headers=api_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["meta"]["total"] == 267
    assert len(body["features"]) == 50  # default page_size
    assert body["features"][0]["type"] == "Feature"


def test_list_stations_filter_matching_nothing_returns_empty_features(api_headers):
    response = client.get(
        "/v1/stations", headers=api_headers, params={"neighborhood": "Bairro Que Nao Existe"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["features"] == []
    assert body["meta"]["total"] == 0


def test_list_stations_filters_by_status(api_headers):
    response = client.get(
        "/v1/stations", headers=api_headers, params={"status": "existente_3_0"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 2
    assert all(f["properties"]["status"] == "existente_3_0" for f in body["features"])


def test_get_station_by_id_returns_feature(api_headers):
    listed = client.get("/v1/stations", headers=api_headers, params={"page_size": 1}).json()
    real_id = listed["features"][0]["properties"]["id"]

    response = client.get(f"/v1/stations/{real_id}", headers=api_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "Feature"
    assert body["properties"]["id"] == real_id


def test_get_station_by_id_404_for_missing_id(api_headers):
    response = client.get("/v1/stations/10000000", headers=api_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
