import dataclasses
import hashlib
import json
import logging

from meli_api.application.ports.cache import Cache
from meli_api.application.ports.product_repository import ProductRepository
from meli_api.domain.product import EnrichmentStatus, Product

logger = logging.getLogger("meli_api.cached_repository")


def _product_to_dict(product: Product) -> dict:
    data = dataclasses.asdict(product)
    data["status"] = product.status.value
    return data


def _product_from_dict(data: dict) -> Product:
    return Product(**{**data, "status": EnrichmentStatus(data["status"])})


def _list_cache_key(
    status: EnrichmentStatus | None, query: str | None, limit: int, offset: int
) -> str:
    raw = f"{status.value if status else ''}|{query or ''}|{limit}|{offset}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"products:list:{digest}"


class CachedProductRepository:
    """Decorador cache-aside sobre un `ProductRepository` real.

    Implementa el mismo puerto que envuelve, así que para `application/` (los
    use cases) es indistinguible de un repositorio sin cache -- ni siquiera
    saben que Redis existe. Cualquier problema con el valor cacheado (JSON
    corrupto, campos inesperados) se trata como cache-miss en vez de propagar
    el error: el cache nunca debe ser la causa de que la API falle.
    """

    def __init__(
        self,
        repository: ProductRepository,
        cache: Cache,
        detail_ttl_seconds: int,
        list_ttl_seconds: int,
    ):
        self._repository = repository
        self._cache = cache
        self._detail_ttl = detail_ttl_seconds
        self._list_ttl = list_ttl_seconds

    def get_by_id(self, item_id: str) -> Product | None:
        key = f"product:{item_id}"
        cached = self._read_cached_product(key)
        if cached is not None:
            return cached

        product = self._repository.get_by_id(item_id)
        if product is not None:
            self._cache.set(key, json.dumps(_product_to_dict(product)), self._detail_ttl)
        return product

    def list(
        self,
        status: EnrichmentStatus | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Product], int]:
        key = _list_cache_key(status, query, limit, offset)
        cached = self._read_cached_page(key)
        if cached is not None:
            return cached

        items, total = self._repository.list(
            status=status, query=query, limit=limit, offset=offset
        )
        payload = {"items": [_product_to_dict(p) for p in items], "total": total}
        self._cache.set(key, json.dumps(payload), self._list_ttl)
        return items, total

    def _read_cached_product(self, key: str) -> Product | None:
        raw = self._cache.get(key)
        if raw is None:
            return None
        try:
            return _product_from_dict(json.loads(raw))
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("Valor de cache corrupto para %r, se ignora: %s", key, exc)
            return None

    def _read_cached_page(self, key: str) -> tuple[list[Product], int] | None:
        raw = self._cache.get(key)
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            items = [_product_from_dict(item) for item in payload["items"]]
            return items, payload["total"]
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("Valor de cache corrupto para %r, se ignora: %s", key, exc)
            return None
