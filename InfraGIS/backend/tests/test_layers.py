import json

from fastapi.testclient import TestClient

from app.models import Layer, LayerSourceType


def test_layers_unauthorized(client: TestClient):
    r = client.get("/layers")
    assert r.status_code == 401


def test_layers_empty(client: TestClient):
    t = client.post("/auth/login", json={"login": "admin", "password": "adminpass"}).json()["access_token"]
    r = client.get("/layers", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert r.json() == []


def test_create_layer_upload_and_geojson(client: TestClient, db):
    t = client.post("/auth/login", json={"login": "admin", "password": "adminpass"}).json()["access_token"]
    geo = {"type": "FeatureCollection", "features": []}
    files = {"file": ("test.geojson", json.dumps(geo).encode(), "application/geo+json")}
    data = {"name": "Test layer", "description": "d"}
    r = client.post(
        "/layers",
        headers={"Authorization": f"Bearer {t}"},
        data=data,
        files=files,
    )
    assert r.status_code == 201, r.text
    lid = r.json()["id"]

    g = client.get(f"/layers/{lid}/geojson", headers={"Authorization": f"Bearer {t}"})
    assert g.status_code == 200
    assert g.json()["type"] == "FeatureCollection"

    layer = db.get(Layer, lid)
    assert layer is not None
    assert layer.source_type == LayerSourceType.uploaded_geojson
