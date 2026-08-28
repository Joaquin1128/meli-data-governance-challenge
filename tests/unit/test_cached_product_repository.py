from meli_api.adapters.outbound.persistence.cached_product_repository import (
    CachedProductRepository,
)
from meli_api.domain.product import EnrichmentStatus
from tests.unit.fakes import FakeProductRepository, make_product


class FakeCache:
    """Doble en memoria del puerto Cache, con contadores para verificar el
    patrón cache-aside (cuántas veces se llamó get/set)."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self.get_calls = 0
        self.set_calls = 0

    def get(self, key: str) -> str | None:
        self.get_calls += 1
        return self._store.get(key)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self.set_calls += 1
        self._store[key] = value

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def status(self) -> str:
        return "ok"


def test_get_by_id_populates_cache_on_miss_and_reads_from_it_on_hit():
    underlying = FakeProductRepository([make_product(item_id="MLA1")])
    cache = FakeCache()
    repository = CachedProductRepository(underlying, cache, detail_ttl_seconds=300, list_ttl_seconds=60)

    first = repository.get_by_id("MLA1")
    underlying._products.clear()  # si viniera de la DB real, esto ahora fallaría
    second = repository.get_by_id("MLA1")

    assert first.item_id == second.item_id == "MLA1"
    assert cache.set_calls == 1


def test_get_by_id_does_not_cache_a_missing_product():
    underlying = FakeProductRepository([])
    cache = FakeCache()
    repository = CachedProductRepository(underlying, cache, detail_ttl_seconds=300, list_ttl_seconds=60)

    assert repository.get_by_id("MLA-inexistente") is None
    assert cache.set_calls == 0


def test_corrupted_cache_value_is_treated_as_a_miss():
    underlying = FakeProductRepository([make_product(item_id="MLA1")])
    cache = FakeCache()
    cache._store["product:MLA1"] = "no es json válido"
    repository = CachedProductRepository(underlying, cache, detail_ttl_seconds=300, list_ttl_seconds=60)

    product = repository.get_by_id("MLA1")

    assert product is not None
    assert product.item_id == "MLA1"


def test_list_caches_by_the_full_filter_combination():
    underlying = FakeProductRepository(
        [make_product(item_id="MLA1", status=EnrichmentStatus.ENRICHED)]
    )
    cache = FakeCache()
    repository = CachedProductRepository(underlying, cache, detail_ttl_seconds=300, list_ttl_seconds=60)

    items_a, total_a = repository.list(status=EnrichmentStatus.ENRICHED, query=None, limit=20, offset=0)
    # Un filtro distinto no debe pegarle a la misma entrada de cache.
    items_b, total_b = repository.list(status=EnrichmentStatus.ERROR, query=None, limit=20, offset=0)

    assert total_a == 1 and len(items_a) == 1
    assert total_b == 0 and len(items_b) == 0
    assert cache.set_calls == 2

    underlying._products.clear()
    items_a_cached, total_a_cached = repository.list(
        status=EnrichmentStatus.ENRICHED, query=None, limit=20, offset=0
    )
    assert total_a_cached == 1
    assert items_a_cached[0].item_id == "MLA1"
