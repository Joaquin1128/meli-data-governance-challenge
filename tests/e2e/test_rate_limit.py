import pytest
from fastapi.testclient import TestClient

from meli_api.adapters.inbound.http.app import create_app
from meli_api.config.settings import get_settings


@pytest.fixture
def low_limit_client(seeded_db_path: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Cliente con un límite de 2 requests/minuto en vez del default (60), para
    poder disparar un 429 en un test rápido sin esperar un minuto real ni pegarle
    60 veces al endpoint.

    `default_rate_limit()` (en rate_limit.py) llama a `get_settings()`
    directamente -- no vía `Depends` -- así que un `app.dependency_overrides` no
    lo afecta: hay que tocar la variable de entorno y limpiar el `lru_cache` de
    `get_settings` explícitamente.
    """
    monkeypatch.setenv("MELI_API_DB_PATH", seeded_db_path)
    monkeypatch.setenv("MELI_API_CACHE_BACKEND", "none")
    monkeypatch.setenv("MELI_API_RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)
    yield client

    get_settings.cache_clear()  # no contaminar el resto de la suite con este override


def test_exceeding_the_rate_limit_returns_429_with_descriptive_body(low_limit_client):
    low_limit_client.get("/products/MLA1")
    low_limit_client.get("/products/MLA1")

    response = low_limit_client.get("/products/MLA1")

    assert response.status_code == 429
    body = response.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_health_and_metrics_are_not_rate_limited(low_limit_client):
    for _ in range(5):
        assert low_limit_client.get("/health").status_code in (200, 503)
        assert low_limit_client.get("/metrics").status_code == 200
