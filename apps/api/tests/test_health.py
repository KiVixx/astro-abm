from __future__ import annotations

from fastapi.testclient import TestClient

from astro_abm_api.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "astro-abm-api"}


def test_local_web_delete_preflight_is_allowed() -> None:
    client = TestClient(app)

    response = client.options(
        "/scenarios/demo_scenario",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "DELETE",
        },
    )

    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
