import json

from fastapi.testclient import TestClient


def _token(client: TestClient, login: str, password: str) -> str:
    # Helper to keep tests concise when acquiring JWT.
    return client.post("/auth/login", json={"login": login, "password": password}).json()["access_token"]


def test_media360_upload_exported_and_playback_ready(client: TestClient):
    # Exported file should be immediately playable without processing queue.
    t = _token(client, "admin", "adminpass")
    files = {"file": ("sample.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")}
    r = client.post("/media360/upload", headers={"Authorization": f"Bearer {t}"}, files=files)
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["source_type"] == "exported"
    media_id = item["id"]

    p = client.get(f"/media360/items/{media_id}/playback", headers={"Authorization": f"Bearer {t}"})
    assert p.status_code == 200
    assert p.json()["status"] == "ready"
    assert p.json()["stream_url"] is not None


def test_media360_upload_raw_then_simulate_ready(client: TestClient):
    # Raw .360 starts pending and becomes ready after simulated processing.
    t = _token(client, "admin", "adminpass")
    files = {"file": ("sample.360", b"raw-go-pro", "application/octet-stream")}
    r = client.post("/media360/upload", headers={"Authorization": f"Bearer {t}"}, files=files)
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["source_type"] == "raw360"
    media_id = item["id"]
    job_id = item["jobs"][0]["id"]

    p0 = client.get(f"/media360/items/{media_id}/playback", headers={"Authorization": f"Bearer {t}"})
    assert p0.status_code == 200
    assert p0.json()["status"] == "pending"

    sim = client.post(f"/media360/internal/jobs/{job_id}/simulate-ready", headers={"Authorization": f"Bearer {t}"})
    assert sim.status_code == 200, sim.text
    assert sim.json()["stage"] == "ready"

    p1 = client.get(f"/media360/items/{media_id}/playback", headers={"Authorization": f"Bearer {t}"})
    assert p1.status_code == 200
    assert p1.json()["status"] == "ready"


def test_media360_simulate_ready_forbidden_for_viewer(viewer_client: TestClient):
    # Internal endpoint must not be callable by non-admin users.
    admin_token = _token(viewer_client, "admin", "adminpass")
    viewer_token = _token(viewer_client, "viewer1", "viewerpass")

    created = viewer_client.post(
        "/media360/upload",
        headers={"Authorization": f"Bearer {viewer_token}"},
        files={"file": ("sample.360", b"raw-go-pro", "application/octet-stream")},
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["jobs"][0]["id"]

    denied = viewer_client.post(
        f"/media360/internal/jobs/{job_id}/simulate-ready",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert denied.status_code == 403

    allowed = viewer_client.post(
        f"/media360/internal/jobs/{job_id}/simulate-ready",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 200


def test_media360_geolink_and_map_points(client: TestClient):
    # Geolink creation should expose media in map-points response.
    t = _token(client, "admin", "adminpass")
    files = {"file": ("sample.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")}
    created = client.post("/media360/upload", headers={"Authorization": f"Bearer {t}"}, files=files)
    media_id = created.json()["id"]

    link = client.post(
        f"/media360/items/{media_id}/geolink",
        headers={"Authorization": f"Bearer {t}"},
        json={"lon": 37.62, "lat": 55.75, "heading": 180, "pitch": 0},
    )
    assert link.status_code == 200, link.text

    points = client.get("/media360/map-points", headers={"Authorization": f"Bearer {t}"})
    assert points.status_code == 200
    assert any(row["media_id"] == media_id for row in points.json())


def test_media360_geolink_chainage_by_axis(client: TestClient):
    t = _token(client, "admin", "adminpass")
    road = client.post(
        "/layers/roads",
        headers={"Authorization": f"Bearer {t}"},
        json={"name": "M-11"},
    )
    assert road.status_code == 201, road.text
    geo = {"type": "LineString", "coordinates": [[37.0, 55.0], [37.2, 55.0]]}
    axis = client.post(
        f"/layers/{road.json()['id']}/axis",
        headers={"Authorization": f"Bearer {t}"},
        files={"file": ("axis.geojson", json.dumps(geo).encode("utf-8"), "application/geo+json")},
    )
    assert axis.status_code == 201, axis.text
    axis_id = axis.json()["id"]

    files = {"file": ("sample.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")}
    created = client.post("/media360/upload", headers={"Authorization": f"Bearer {t}"}, files=files)
    assert created.status_code == 201, created.text
    media_id = created.json()["id"]

    link = client.post(
        f"/media360/items/{media_id}/geolink",
        headers={"Authorization": f"Bearer {t}"},
        json={"lon": 37.1, "lat": 55.0, "axis_layer_id": axis_id},
    )
    assert link.status_code == 200, link.text
    payload = link.json()
    assert payload["axis_layer_id"] == axis_id
    assert payload["axis_km"] is not None
    assert payload["axis_km"] > 0


def test_media360_map_points_scoped_for_viewer(viewer_client: TestClient):
    # Viewer cannot see map points belonging to other users.
    admin_token = _token(viewer_client, "admin", "adminpass")
    viewer_token = _token(viewer_client, "viewer1", "viewerpass")

    created = viewer_client.post(
        "/media360/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")},
    )
    assert created.status_code == 201, created.text
    media_id = created.json()["id"]

    linked = viewer_client.post(
        f"/media360/items/{media_id}/geolink",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"lon": 37.62, "lat": 55.75},
    )
    assert linked.status_code == 200, linked.text

    viewer_points = viewer_client.get("/media360/map-points", headers={"Authorization": f"Bearer {viewer_token}"})
    assert viewer_points.status_code == 200
    assert all(row["media_id"] != media_id for row in viewer_points.json())

    admin_points = viewer_client.get("/media360/map-points", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_points.status_code == 200
    assert any(row["media_id"] == media_id for row in admin_points.json())


def test_media360_recalculate_axis_km_bulk(client: TestClient):
    t = _token(client, "admin", "adminpass")
    road = client.post("/layers/roads", headers={"Authorization": f"Bearer {t}"}, json={"name": "M-12"})
    assert road.status_code == 201, road.text
    geo = {"type": "LineString", "coordinates": [[37.0, 55.0], [37.3, 55.0]]}
    axis = client.post(
        f"/layers/{road.json()['id']}/axis",
        headers={"Authorization": f"Bearer {t}"},
        files={"file": ("axis.geojson", json.dumps(geo).encode("utf-8"), "application/geo+json")},
    )
    assert axis.status_code == 201, axis.text
    axis_id = axis.json()["id"]

    created = client.post(
        "/media360/upload",
        headers={"Authorization": f"Bearer {t}"},
        files={"file": ("sample.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")},
    )
    assert created.status_code == 201, created.text
    media_id = created.json()["id"]
    link = client.post(
        f"/media360/items/{media_id}/geolink",
        headers={"Authorization": f"Bearer {t}"},
        json={"lon": 37.1, "lat": 55.0, "axis_layer_id": axis_id},
    )
    assert link.status_code == 200, link.text

    recalc = client.post(
        f"/media360/axis/{axis_id}/recalculate-km",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert recalc.status_code == 200, recalc.text
    payload = recalc.json()
    assert payload["axis_layer_id"] == axis_id
    assert payload["scanned"] >= 1
    assert payload["recalculated"] >= 1


def test_media360_recalculate_axis_km_forbidden_for_viewer(viewer_client: TestClient):
    admin_token = _token(viewer_client, "admin", "adminpass")
    viewer_token = _token(viewer_client, "viewer1", "viewerpass")
    road = viewer_client.post("/layers/roads", headers={"Authorization": f"Bearer {admin_token}"}, json={"name": "M-13"})
    axis = viewer_client.post(
        f"/layers/{road.json()['id']}/axis",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("axis.geojson", json.dumps({'type': 'LineString', 'coordinates': [[37.0, 55.0], [37.2, 55.0]]}).encode('utf-8'), "application/geo+json")},
    )
    denied = viewer_client.post(
        f"/media360/axis/{axis.json()['id']}/recalculate-km",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert denied.status_code == 403
