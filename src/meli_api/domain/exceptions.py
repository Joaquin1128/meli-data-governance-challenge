class DomainError(Exception):
    """Base de todas las excepciones de dominio de la API."""


class ProductNotFoundError(DomainError):
    def __init__(self, item_id: str):
        super().__init__(f"Producto '{item_id}' no encontrado")
        self.item_id = item_id


class RepositoryUnavailableError(DomainError):
    """La fuente de verdad (SQLite) no pudo ser consultada.

    No existe fallback razonable para esta falla: es la única fuente de datos de la
    API. El adapter HTTP la traduce a un 503 descriptivo.
    """

    def __init__(self, reason: str):
        super().__init__(f"Repositorio de productos no disponible: {reason}")
        self.reason = reason


class InvalidFilterError(DomainError):
    """Parámetros de filtro/paginación inválidos (ej. status inexistente, limit <= 0)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
