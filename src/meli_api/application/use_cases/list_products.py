from dataclasses import dataclass

from meli_api.application.ports.product_repository import ProductRepository
from meli_api.domain.exceptions import InvalidFilterError
from meli_api.domain.product import EnrichmentStatus, Product

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@dataclass(frozen=True)
class ProductPage:
    """Página de resultados + metadata para que el adapter HTTP arme la respuesta
    paginada sin volver a tocar el repositorio."""

    items: list[Product]
    total: int
    limit: int
    offset: int


class ListProducts:
    """Caso de uso: listar productos paginados, filtrando por status y/o texto
    en el nombre. Valida los parámetros de paginación acá (no en el adapter HTTP
    ni en el repositorio) para que la regla sea la misma sin importar quién llame
    al caso de uso."""

    def __init__(self, repository: ProductRepository):
        self._repository = repository

    def execute(
        self,
        status: EnrichmentStatus | None = None,
        query: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> ProductPage:
        if not (1 <= limit <= MAX_LIMIT):
            raise InvalidFilterError(f"'limit' debe estar entre 1 y {MAX_LIMIT}")
        if offset < 0:
            raise InvalidFilterError("'offset' no puede ser negativo")

        items, total = self._repository.list(
            status=status, query=query, limit=limit, offset=offset
        )
        return ProductPage(items=items, total=total, limit=limit, offset=offset)
