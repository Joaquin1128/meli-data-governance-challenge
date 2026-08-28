from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from meli_api.adapters.outbound.persistence.sqlite_repository import (
    SqliteProductRepository,
)
from meli_api.application.ports.product_repository import ProductRepository
from meli_api.application.use_cases.get_product import GetProductById
from meli_api.application.use_cases.list_products import ListProducts
from meli_api.config.settings import Settings, get_settings


@lru_cache
def _repository_for(db_path: str) -> ProductRepository:
    """El adapter concreto es el único lugar que sabe que hoy es SQLite.

    Cachear por `db_path` (no una única instancia global) mantiene testeable la
    inyección de dependencias: los tests de e2e pueden overridear `get_settings`
    con otro `db_path` y obtienen un repositorio distinto sin reiniciar el proceso.
    """
    return SqliteProductRepository(db_path)


def get_product_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProductRepository:
    return _repository_for(settings.db_path)


def get_get_product_use_case(
    repository: Annotated[ProductRepository, Depends(get_product_repository)],
) -> GetProductById:
    return GetProductById(repository)


def get_list_products_use_case(
    repository: Annotated[ProductRepository, Depends(get_product_repository)],
) -> ListProducts:
    return ListProducts(repository)
