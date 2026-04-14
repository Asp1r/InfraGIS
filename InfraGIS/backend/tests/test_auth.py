from fastapi.testclient import TestClient


def test_login_ok(client: TestClient):
    r = client.post("/auth/login", json={"login": "admin", "password": "adminpass"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient):
    r = client.post("/auth/login", json={"login": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_token(client: TestClient):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_token(client: TestClient):
    t = client.post("/auth/login", json={"login": "admin", "password": "adminpass"}).json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert r.json()["login"] == "admin"
    assert r.json()["role"] == "admin"


def test_admin_users_forbidden_for_viewer(viewer_client: TestClient):
    t = viewer_client.post("/auth/login", json={"login": "viewer1", "password": "viewerpass"}).json()[
        "access_token"
    ]
    r = viewer_client.get("/admin/users", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403
