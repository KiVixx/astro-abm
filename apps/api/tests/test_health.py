from __future__ import annotations

from fastapi.testclient import TestClient

from astro_abm_api.main import app, create_app


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
    assert response.headers["access-control-allow-credentials"] == "true"


def test_local_web_preset_update_preflight_is_allowed() -> None:
    client = TestClient(app)

    for origin in ("http://127.0.0.1:3000", "http://localhost:3000"):
        response = client.options(
            "/llm/presets/local_preset",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert "PUT" in response.headers["access-control-allow-methods"]
        assert response.headers["access-control-allow-origin"] == origin


def test_production_cors_uses_only_configured_origins(monkeypatch) -> None:
    monkeypatch.setenv("ASTRO_ABM_ENV", "production")
    monkeypatch.setenv("ASTRO_ABM_ALLOWED_ORIGINS", "https://astro.example")
    client = TestClient(create_app())

    allowed = client.options(
        "/auth/login",
        headers={
            "Origin": "https://astro.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    rejected = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://astro.example"
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers
