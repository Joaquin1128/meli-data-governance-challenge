from typing import Annotated

from fastapi import APIRouter, Depends, Query

from meli_api.adapters.inbound.http.dependencies import (
    get_get_product_use_case,
    get_list_products_use_case,
)
from meli_api.adapters.inbound.http.schemas import ProductListResponse, ProductResponse
from meli_api.application.use_cases.get_product import GetProductById
from meli_api.application.use_cases.list_products import DEFAULT_LIMIT, ListProducts
from meli_api.domain.product import EnrichmentStatus

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
def list_products(
    use_case: Annotated[ListProducts, Depends(get_list_products_use_case)],
    status: Annotated[
        EnrichmentStatus | None,
        Query(description="Filtra por estado de enriquecimiento."),
    ] = None,
    q: Annotated[
        str | None, Query(description="Búsqueda de texto libre en el nombre del producto.")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Tamaño de página.")] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0, description="Cantidad de resultados a saltear.")] = 0,
) -> ProductListResponse:
    page = use_case.execute(status=status, query=q, limit=limit, offset=offset)
    return ProductListResponse.from_page(page)


@router.get("/{item_id}", response_model=ProductResponse)
def get_product(
    item_id: str,
    use_case: Annotated[GetProductById, Depends(get_get_product_use_case)],
) -> ProductResponse:
    product = use_case.execute(item_id)
    return ProductResponse.from_domain(product)
