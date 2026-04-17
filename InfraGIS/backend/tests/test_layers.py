import csv
import io
import json
import zipfile

from fastapi.testclient import TestClient
import shapefile

from app.models import Layer, LayerKind, LayerSourceType


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
    assert layer.kind == LayerKind.road


def test_create_road_and_tree(client: TestClient):
    t = client.post("/auth/login", json={"login": "admin", "password": "adminpass"}).json()["access_token"]
    road = client.post(
        "/layers/roads",
        headers={"Authorization": f"Bearer {t}"},
        json={"name": "A-108", "description": "Тестовая дорога"},
    )
    assert road.status_code == 201, road.text
    tree = client.get("/layers/tree", headers={"Authorization": f"Bearer {t}"})
    assert tree.status_code == 200
    data = tree.json()
    assert len(data) == 1
    assert data[0]["kind"] == "road"
    assert data[0]["children"] == []


def test_upload_axis_from_geojson(client: TestClient):
    t = client.post("/auth/login", json={"login": "admin", "password": "adminpass"}).json()["access_token"]
    road = client.post(
        "/layers/roads",
        headers={"Authorization": f"Bearer {t}"},
        json={"name": "M-4"},
    ).json()
    geo = {"type": "LineString", "coordinates": [[37.0, 55.0], [37.1, 55.0], [37.2, 55.0]]}
    files = {"file": ("axis.geojson", json.dumps(geo).encode("utf-8"), "application/geo+json")}
    res = client.post(
        f"/layers/{road['id']}/axis",
        headers={"Authorization": f"Bearer {t}"},
        data={"name": "Ось"},
        files=files,
    )
    assert res.status_code == 201, res.text
    payload = res.json()
    assert payload["kind"] == "road_axis"
    assert payload["total_km"] > 0
    assert len(payload["points"]) == 3


def test_upload_axis_from_csv(client: TestClient):
    t = client.post("/auth/login", json={"login": "admin", "password": "adminpass"}).json()["access_token"]
    road = client.post(
        "/layers/roads",
        headers={"Authorization": f"Bearer {t}"},
        json={"name": "A-107"},
    ).json()
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["order", "lon", "lat"])
    writer.writeheader()
    writer.writerow({"order": 2, "lon": 37.2, "lat": 55.0})
    writer.writerow({"order": 1, "lon": 37.0, "lat": 55.0})
    writer.writerow({"order": 3, "lon": 37.3, "lat": 55.0})
    files = {"file": ("axis.csv", out.getvalue().encode("utf-8"), "text/csv")}
    res = client.post(
        f"/layers/{road['id']}/axis",
        headers={"Authorization": f"Bearer {t}"},
        files=files,
    )
    assert res.status_code == 201, res.text
    payload = res.json()
    assert payload["kind"] == "road_axis"
    assert payload["points"][0]["lon"] == 37.0


def test_upload_axis_from_shapefile_zip(client: TestClient):
    t = client.post("/auth/login", json={"login": "admin", "password": "adminpass"}).json()["access_token"]
    road = client.post(
        "/layers/roads",
        headers={"Authorization": f"Bearer {t}"},
        json={"name": "A-105"},
    ).json()

    shp_buf = io.BytesIO()
    shx_buf = io.BytesIO()
    dbf_buf = io.BytesIO()
    writer = shapefile.Writer(shp=shp_buf, shx=shx_buf, dbf=dbf_buf)
    writer.field("name", "C")
    writer.line([[[37.0, 55.0], [37.05, 55.0], [37.1, 55.0]]])
    writer.record("axis")
    writer.close()
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("axis.shp", shp_buf.getvalue())
        zf.writestr("axis.shx", shx_buf.getvalue())
        zf.writestr("axis.dbf", dbf_buf.getvalue())
    files = {"file": ("axis.zip", zip_buf.getvalue(), "application/zip")}
    res = client.post(
        f"/layers/{road['id']}/axis",
        headers={"Authorization": f"Bearer {t}"},
        files=files,
    )
    assert res.status_code == 201, res.text
    assert res.json()["kind"] == "road_axis"


def test_create_iri_and_defect_records(client: TestClient):
    t = client.post("/auth/login", json={"login": "admin", "password": "adminpass"}).json()["access_token"]
    road = client.post("/layers/roads", headers={"Authorization": f"Bearer {t}"}, json={"name": "R-21"}).json()
    geo = {"type": "LineString", "coordinates": [[37.0, 55.0], [37.2, 55.0]]}
    files = {"file": ("axis.geojson", json.dumps(geo).encode("utf-8"), "application/geo+json")}
    axis = client.post(f"/layers/{road['id']}/axis", headers={"Authorization": f"Bearer {t}"}, files=files).json()

    iri_layer = client.post(
        "/layers",
        headers={"Authorization": f"Bearer {t}"},
        data={
            "name": "IRI",
            "kind": "iri",
            "parent_id": str(road["id"]),
            "axis_layer_id": str(axis["id"]),
        },
    ).json()
    defect_layer = client.post(
        "/layers",
        headers={"Authorization": f"Bearer {t}"},
        data={
            "name": "Defects",
            "kind": "defects",
            "parent_id": str(road["id"]),
            "axis_layer_id": str(axis["id"]),
        },
    ).json()

    iri_res = client.post(
        "/layers/iri-records",
        headers={"Authorization": f"Bearer {t}"},
        json={
            "layer_id": iri_layer["id"],
            "axis_layer_id": axis["id"],
            "km_start": 0.1,
            "km_end": 0.8,
            "iri_value": 2.4,
            "direction": "forward",
            "lane": "1",
        },
    )
    assert iri_res.status_code == 201, iri_res.text

    defect_res = client.post(
        "/layers/defect-records",
        headers={"Authorization": f"Bearer {t}"},
        json={
            "layer_id": defect_layer["id"],
            "axis_layer_id": axis["id"],
            "defect_code": "pothole",
            "severity": "medium",
            "norm_ref": "GOST R 50597-2017",
            "km_start": 0.3,
            "km_end": 0.32,
            "extent_m": 18.0,
        },
    )
    assert defect_res.status_code == 201, defect_res.text
