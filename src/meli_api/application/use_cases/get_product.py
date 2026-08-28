from meli_api.application.ports.product_repository import ProductRepository
from meli_api.domain.exceptions import ProductNotFoundError
from meli_api.domain.product import Product


class GetProductById:
    """Caso de uso: obtener el detalle de un producto por id.

    No sabe si `repository` es SQLite, Postgres o un fake de test: solo conoce
    el puerto `ProductRepository`.
    """

    def __init__(self, repository: ProductRepository):
        self._repository = repository

    def execute(self, item_id: str) -> Product:
        product = self._repository.get_by_id(item_id)
        if product is None:
            raise ProductNotFoundError(item_id)
        return product
