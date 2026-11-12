from fastapi.testclient import TestClient


def test_post_login_without_csrf_403(client: TestClient) -> None:
    r = client.post("/auth/login", data={"username": "x", "password": "y"})
    assert r.status_code == 403
