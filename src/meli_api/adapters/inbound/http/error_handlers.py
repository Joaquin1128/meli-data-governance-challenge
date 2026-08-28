import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from meli_api.domain.exceptions import (
    InvalidFilterError,
    ProductNotFoundError,
    RepositoryUnavailableError,
)

logger = logging.getLogger("meli_api.errors")


def _error(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    """Centraliza el mapeo excepción de dominio -> respuesta HTTP.

    Los use cases y adapters de salida nunca conocen FastAPI ni construyen
    respuestas HTTP: solo lanzan excepciones de `domain.exceptions`. Este es el
    único lugar que traduce eso a códigos de estado y JSON.
    """

    @app.exception_handler(ProductNotFoundError)
    async def _not_found(request: Request, exc: ProductNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=_error("PRODUCT_NOT_FOUND", str(exc)),
        )

    @app.exception_handler(InvalidFilterError)
    async def _invalid_filter(request: Request, exc: InvalidFilterError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error("INVALID_FILTER", str(exc)),
        )

    @app.exception_handler(RepositoryUnavailableError)
    async def _repository_unavailable(
        request: Request, exc: RepositoryUnavailableError
    ) -> JSONResponse:
        logger.error("Repositorio de productos no disponible: %s", exc.reason)
        return JSONResponse(
            status_code=503,
            content=_error(
                "REPOSITORY_UNAVAILABLE",
                "El almacenamiento de productos no está disponible en este momento.",
            ),
        )

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no controlado atendiendo %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content=_error("INTERNAL_ERROR", "Ocurrió un error inesperado."),
        )
