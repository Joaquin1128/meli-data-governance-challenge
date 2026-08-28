import json
import sqlite3
from pathlib import Path

import pytest

_CREATE_TABLE = """
CREATE TABLE products (
    item_id TEXT PRIMARY KEY,
    name TEXT,
    price REAL,
    currency TEXT,
    image_url TEXT,
    permalink TEXT,
    rating REAL,
    original_description TEXT,
    specifications_json TEXT,
    enriched_description TEXT,
    status TEXT,
    error_message TEXT,
    created_at TEXT,
    updated_at TEXT
)
"""


def _insert(conn: sqlite3.Connection, **row) -> None:
    defaults = dict(
        price=None,
        currency=None,
        image_url=None,
        permalink=None,
        rating=None,
        original_description="",
        specifications=None,
        enriched_description=None,
        status="pending",
        error_message=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    defaults.update(row)
    specifications_json = (
        json.dumps(defaults.pop("specifications")) if defaults["specifications"] else None
    )
    conn.execute(
        """
        INSERT INTO products (
            item_id, name, price, currency, image_url, permalink, rating,
            original_description, specifications_json, enriched_description,
            status, error_message, created_at, updated_at
        ) VALUES (:item_id, :name, :price, :currency, :image_url, :permalink, :rating,
                  :original_description, :specifications_json, :enriched_description,
                  :status, :error_message, :created_at, :updated_at)
        """,
        {**defaults, "specifications_json": specifications_json},
    )


@pytest.fixture
def seeded_db_path(tmp_path: Path) -> str:
    """Crea una SQLite temporal con el mismo esquema que produce el pipeline
    offline (notebooks/meli_enrichment_pipeline.ipynb), poblada con casos que
    ejercitan cada status de enriquecimiento."""
    db_path = tmp_path / "meli_products_test.db"
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute(_CREATE_TABLE)
        _insert(
            conn,
            item_id="MLA1",
            name="Notebook Gamer X",
            price=1500.0,
            currency="ARS",
            original_description="original corta",
            enriched_description="Descripción enriquecida por Gemini.",
            specifications={"RAM": "16GB"},
            status="enriched",
        )
        _insert(
            conn,
            item_id="MLA2",
            name="Mouse Inalámbrico",
            price=20.0,
            currency="ARS",
            original_description="Ya tenía una descripción larga y completa de fábrica.",
            status="skipped",
        )
        _insert(
            conn,
            item_id="MLA3",
            name="Teclado Mecánico",
            original_description="original",
            status="error",
            error_message="Gemini timeout",
        )
    conn.close()
    return str(db_path)
