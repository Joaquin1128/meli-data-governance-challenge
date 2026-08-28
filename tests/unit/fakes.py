from meli_api.domain.product import EnrichmentStatus, Product


def make_product(item_id: str = "MLA1", **overrides) -> Product:
    """Factory de Product con defaults razonables, para no repetir todos los
    campos obligatorios en cada test."""
    defaults = dict(
        item_id=item_id,
        name="Producto de prueba",
        price=100.0,
        currency="ARS",
        image_url="https://example.com/img.jpg",
        permalink="https://example.com/item",
        rating=None,
        original_description="descripción original",
        enriched_description=None,
        specifications={},
        status=EnrichmentStatus.PENDING,
    )
    defaults.update(overrides)
    return Product(**defaults)


class FakeProductRepository:
    """Implementación en memoria del puerto ProductRepository, usada solo en tests.

    No es un Mock: implementa el contrato real para que los tests de casos de uso
    ejerciten la lógica de filtrado/paginación tal como lo haría un adapter real.
    """

    def __init__(self, products: list[Product] | None = None):
        self._products = {p.item_id: p for p in (products or [])}

    def get_by_id(self, item_id: str) -> Product | None:
        return self._products.get(item_id)

    def list(
        self,
        status: EnrichmentStatus | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Product], int]:
        results = list(self._products.values())
        if status is not None:
            results = [p for p in results if p.status == status]
        if query:
            results = [p for p in results if query.lower() in p.name.lower()]
        total = len(results)
        return results[offset : offset + limit], total
