import pytest
from fastapi.testclient import TestClient

from meli_api.adapters.inbound.http.app import create_app
from meli_api.adapters.inbound.http.rate_limit import limiter
from meli_api.config.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """El `Limiter` de slowapi es un singleton a nivel módulo (así lo espera la
    librería, para que el decorador `@limiter.limit` en los routers lo
    encuentre); sin resetear su storage entre tests, el conteo de requests se
    acumularía entre tests no relacionados y podría disparar 429s espurios."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client(seeded_db_path: str) -> TestClient:
    """Cliente e2e sobre una app fresca (no el singleton `app` del módulo, que
    resolvería settings reales) apuntando a la SQLite temporal seedeada."""
    app = create_app()
    # cache_backend="none": los tests e2e no deben depender de si hay un Redis
    # real corriendo ni de su latencia; el comportamiento de Redis en sí se
    # cubre en tests/integration/test_redis_cache.py.
    app.dependency_overrides[get_settings] = lambda: Settings(
        db_path=seeded_db_path, cache_backend="none"
    )
    return TestClient(app)
