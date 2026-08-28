from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from meli_api.adapters.inbound.http.dependencies import get_product_repository
from meli_api.application.ports.product_repository import ProductRepository
from meli_api.domain.exceptions import RepositoryUnavailableError

router = APIRouter(tags=["health"])


@router.get("/health")
def health(
    repository: Annotated[ProductRepository, Depends(get_product_repository)],
) -> JSONResponse:
    """Reporta el estado de cada dependencia por separado en vez de un simple
    "ok"/"error": permite distinguir una API sana, una degradada (Redis caído,
    ver Parte 5) y una realmente caída (SQLite no disponible, sin la cual la API
    no puede responder nada útil)."""
    checks: dict[str, str] = {}

    try:
        repository.get_by_id("__health_check__")
        checks["database"] = "ok"
    except RepositoryUnavailableError:
        checks["database"] = "unavailable"

    # El check de Redis se agrega en la Parte 5, cuando exista el adapter de cache.
    checks["cache"] = "not_configured"

    is_healthy = checks["database"] == "ok"
    status_code = 200 if is_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if is_healthy else "degraded", "checks": checks},
    )
