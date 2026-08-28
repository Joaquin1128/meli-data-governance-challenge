from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from meli_api.adapters.outbound.cache.null_cache import NullCache
from meli_api.adapters.outbound.cache.redis_cache import RedisCache
from meli_api.adapters.outbound.persistence.cached_product_repository import (
    CachedProductRepository,
)
from meli_api.adapters.outbound.persistence.sqlite_repository import (
    SqliteProductRepository,
)
from meli_api.application.ports.cache import Cache
from meli_api.application.ports.product_repository import ProductRepository
from meli_api.application.use_cases.get_product import GetProductById
from meli_api.application.use_cases.list_products import ListProducts
from meli_api.config.settings import Settings, get_settings


@lru_cache
def _sqlite_repository_for(db_path: str) -> SqliteProductRepository:
    """El adapter concreto es el único lugar que sabe que hoy es SQLite.

    Cachear por `db_path` (no una única instancia global) mantiene testeable la
    inyección de dependencias: los tests pueden overridear `get_settings` con
    otro `db_path` y obtienen un repositorio distinto sin reiniciar el proceso.
    """
    return SqliteProductRepository(db_path)


@lru_cache
def _redis_cache_for(redis_url: str, fail_max: int, reset_timeout_seconds: int) -> RedisCache:
    return RedisCache(redis_url, fail_max, reset_timeout_seconds)


@lru_cache
def _null_cache() -> NullCache:
    return NullCache()


def get_cache(settings: Annotated[Settings, Depends(get_settings)]) -> Cache:
    if settings.cache_backend == "none":
        return _null_cache()
    return _redis_cache_for(
        settings.redis_url,
        settings.redis_breaker_fail_max,
        settings.redis_breaker_reset_timeout_seconds,
    )


def get_product_repository(
    settings: Annotated[Settings, Depends(get_settings)],
    cache: Annotated[Cache, Depends(get_cache)],
) -> ProductRepository:
    base_repository = _sqlite_repository_for(settings.db_path)
    return CachedProductRepository(
        base_repository,
        cache,
        detail_ttl_seconds=settings.cache_ttl_detail_seconds,
        list_ttl_seconds=settings.cache_ttl_list_seconds,
    )


def get_get_product_use_case(
    repository: Annotated[ProductRepository, Depends(get_product_repository)],
) -> GetProductById:
    return GetProductById(repository)


def get_list_products_use_case(
    repository: Annotated[ProductRepository, Depends(get_product_repository)],
) -> ListProducts:
    return ListProducts(repository)
