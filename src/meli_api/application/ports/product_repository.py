from typing import Protocol

from meli_api.domain.product import EnrichmentStatus, Product


class ProductRepository(Protocol):
    """Puerto de persistencia. Cualquier adapter (SQLite, Postgres, ...) que lo
    implemente es intercambiable sin tocar `application/` ni `domain/`.
    """

    def get_by_id(self, item_id: str) -> Product | None:
        """Devuelve el producto o None si no existe. No lanza si no lo encuentra:
        esa decisión (404 vs. otra cosa) es del caso de uso, no del repositorio."""
        ...

    def list(
        self,
        status: EnrichmentStatus | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Product], int]:
        """Devuelve (página de productos, total de resultados que matchean el filtro
        sin paginar) para poder construir metadata de paginación."""
        ...
