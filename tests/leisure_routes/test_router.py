from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_leisure_routes_requires_api_key():
    response = client.get("/v1/leisure-routes")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"


def test_list_leisure_routes_returns_feature_collection(api_headers):
    response = client.get("/v1/leisure-routes", headers=api_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["meta"]["total"] == 3
    assert body["features"][0]["type"] == "Feature"


def test_list_leisure_routes_rejects_unknown_query_param(api_headers):
    response = client.get("/v1/leisure-routes", headers=api_headers, params={"foo": "bar"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_leisure_routes_rejects_invalid_bbox(api_headers):
    response = client.get(
        "/v1/leisure-routes", headers=api_headers, params={"bbox": "not,a,valid,bbox"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_leisure_routes_rejects_page_size_over_cap(api_headers):
    response = client.get("/v1/leisure-routes", headers=api_headers, params={"page_size": 500})
    assert response.status_code == 422


def test_get_leisure_route_by_id_returns_feature(api_headers):
    listed = client.get(
        "/v1/leisure-routes", headers=api_headers, params={"page_size": 1}
    ).json()
    real_id = listed["features"][0]["properties"]["id"]

    response = client.get(f"/v1/leisure-routes/{real_id}", headers=api_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "Feature"
    assert body["properties"]["id"] == real_id


def test_get_leisure_route_by_id_404_for_missing_id(api_headers):
    response = client.get("/v1/leisure-routes/10000000", headers=api_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
