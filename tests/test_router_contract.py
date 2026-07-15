import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

RESOURCE_PATHS = [
    "/v1/routes",
    "/v1/parking",
    "/v1/stations",
    "/v1/rest-points",
    "/v1/leisure-routes",
]


@pytest.mark.parametrize("path", RESOURCE_PATHS)
def test_list_requires_api_key(path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("path", RESOURCE_PATHS)
def test_list_rejects_unknown_query_param(path, api_headers):
    response = client.get(path, headers=api_headers, params={"foo": "bar"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("path", RESOURCE_PATHS)
def test_list_rejects_invalid_bbox(path, api_headers):
    response = client.get(path, headers=api_headers, params={"bbox": "not,a,valid,bbox"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("path", RESOURCE_PATHS)
def test_list_rejects_page_size_over_cap(path, api_headers):
    response = client.get(path, headers=api_headers, params={"page_size": 500})
    assert response.status_code == 422
