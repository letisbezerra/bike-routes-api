from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_support_points_returns_mixed_feature_collection(api_headers):
    response = client.get("/v1/support-points", headers=api_headers, params={"page_size": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) > 0
    assert set(body["meta"]["total_by_type"].keys()) == {"parking", "station", "rest_point"}
    for feature in body["features"]:
        resource_type = feature["properties"]["resource_type"]
        assert resource_type in ("parking", "station", "rest_point")
        if resource_type == "parking":
            assert "spot_count" in feature["properties"]
        elif resource_type == "station":
            assert "status" in feature["properties"]
        else:
            assert "image_urls" in feature["properties"]


def test_list_support_points_unknown_query_param_returns_422(api_headers):
    response = client.get("/v1/support-points", headers=api_headers, params={"foo": "bar"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_support_points_missing_api_key_returns_401():
    response = client.get("/v1/support-points")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
