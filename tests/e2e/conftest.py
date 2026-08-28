import pytest
from fastapi.testclient import TestClient

from meli_api.adapters.inbound.http.app import create_app
from meli_api.config.settings import Settings, get_settings


@pytest.fixture
def client(seeded_db_path: str) -> TestClient:
    """Cliente e2e sobre una app fresca (no el singleton `app` del módulo, que
    resolvería settings reales) apuntando a la SQLite temporal seedeada."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(db_path=seeded_db_path)
    return TestClient(app)
