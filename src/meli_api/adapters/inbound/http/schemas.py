from pydantic import BaseModel

from meli_api.application.use_cases.list_products import ProductPage
from meli_api.domain.product import EnrichmentStatus, Product


class ProductResponse(BaseModel):
    """DTO de salida HTTP. Deliberadamente separado de `domain.Product`: la forma
    en que la API expone un producto puede evolucionar (versionado, campos
    calculados) sin que eso presione al modelo de dominio."""

    item_id: str
    name: str
    description: str
    enrichment_status: EnrichmentStatus
    price: float | None
    currency: str | None
    image_url: str | None
    permalink: str | None
    rating: float | None
    specifications: dict[str, str]

    @classmethod
    def from_domain(cls, product: Product) -> "ProductResponse":
        return cls(
            item_id=product.item_id,
            name=product.name,
            description=product.description,
            enrichment_status=product.status,
            price=product.price,
            currency=product.currency,
            image_url=product.image_url,
            permalink=product.permalink,
            rating=product.rating,
            specifications=product.specifications,
        )


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page: ProductPage) -> "ProductListResponse":
        return cls(
            items=[ProductResponse.from_domain(p) for p in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
