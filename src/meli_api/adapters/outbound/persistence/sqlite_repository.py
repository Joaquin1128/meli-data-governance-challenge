import json
import logging
import sqlite3
from contextlib import closing

from meli_api.domain.exceptions import RepositoryUnavailableError
from meli_api.domain.product import EnrichmentStatus, Product

logger = logging.getLogger("meli_api.sqlite_repository")

# Columnas en el orden en que las selecciona cada query de este adapter. Se listan
# explícitamente (nunca `SELECT *`) para que un ALTER TABLE en el pipeline no
# desalinee silenciosamente el mapeo a Product.
_COLUMNS = (
    "item_id, name, price, currency, image_url, permalink, rating, "
    "original_description, specifications_json, enriched_description, status"
)


def _row_to_product(row: tuple) -> Product:
    (
        item_id,
        name,
        price,
        currency,
        image_url,
        permalink,
        rating,
        original_description,
        specifications_json,
        enriched_description,
        status,
    ) = row

    try:
        enrichment_status = EnrichmentStatus(status)
    except ValueError:
        logger.warning(
            "Producto %s con status desconocido '%s' en SQLite; se trata como PENDING",
            item_id,
            status,
        )
        enrichment_status = EnrichmentStatus.PENDING

    return Product(
        item_id=item_id,
        name=name or "",
        price=price,
        currency=currency,
        image_url=image_url,
        permalink=permalink,
        rating=rating,
        original_description=original_description or "",
        enriched_description=enriched_description,
        specifications=json.loads(specifications_json) if specifications_json else {},
        status=enrichment_status,
    )


def _escape_like(value: str) -> str:
    """Escapa % y _ para que una búsqueda por texto no interprete comodines SQL
    involuntarios que el usuario haya tipeado (ej. buscar 'discount_50%' literal)."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SqliteProductRepository:
    """Adapter que implementa el puerto `ProductRepository` sobre la SQLite que
    escribe el pipeline offline (`meli_products.db`).

    Abre una conexión nueva por operación en vez de mantener una compartida: las
    conexiones de `sqlite3` no son seguras entre threads por default, y FastAPI
    puede correr este código en distintos threads del pool. Para el volumen de
    este prototipo el costo de abrir/cerrar es despreciable; a mayor escala esto
    se reemplazaría por un pool de conexiones o un driver async (ver docs/architecture.md).
    """

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        try:
            return sqlite3.connect(self._db_path)
        except sqlite3.Error as exc:
            raise RepositoryUnavailableError(str(exc)) from exc

    def get_by_id(self, item_id: str) -> Product | None:
        try:
            with closing(self._connect()) as conn, closing(conn.cursor()) as cursor:
                cursor.execute(
                    f"SELECT {_COLUMNS} FROM products WHERE item_id = ?", (item_id,)
                )
                row = cursor.fetchone()
        except sqlite3.Error as exc:
            raise RepositoryUnavailableError(str(exc)) from exc

        return _row_to_product(row) if row else None

    def list(
        self,
        status: EnrichmentStatus | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Product], int]:
        conditions: list[str] = []
        params: list[object] = []

        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        if query:
            conditions.append("name LIKE ? ESCAPE '\\'")
            params.append(f"%{_escape_like(query)}%")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        try:
            with closing(self._connect()) as conn, closing(conn.cursor()) as cursor:
                cursor.execute(
                    f"SELECT COUNT(*) FROM products {where_clause}", params
                )
                total = cursor.fetchone()[0]

                cursor.execute(
                    f"SELECT {_COLUMNS} FROM products {where_clause} "
                    "ORDER BY item_id LIMIT ? OFFSET ?",
                    (*params, limit, offset),
                )
                rows = cursor.fetchall()
        except sqlite3.Error as exc:
            raise RepositoryUnavailableError(str(exc)) from exc

        return [_row_to_product(row) for row in rows], total
