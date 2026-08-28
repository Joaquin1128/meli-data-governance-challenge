import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from meli_api.observability.metrics import record_http_request

access_logger = logging.getLogger("meli_api.access")


def _path_template(request: Request) -> str:
    """Usa el patrón de ruta ('/products/{item_id}'), no la URL concreta, para
    no explotar la cardinalidad de las métricas ni de los logs con un item_id
    distinto por serie."""
    route = request.scope.get("route")
    return route.path if route is not None else request.url.path


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """Un único punto que loguea y mide cada request: nadie más en la app
    necesita saber sobre request_id, latencia o métricas de HTTP."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        duration_seconds = time.perf_counter() - start
        path_template = _path_template(request)

        response.headers["X-Request-ID"] = request_id
        record_http_request(request.method, path_template, response.status_code, duration_seconds)

        log_level = logging.WARNING if response.status_code >= 500 else logging.INFO
        access_logger.log(
            log_level,
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": path_template,
                "status_code": response.status_code,
                "duration_ms": round(duration_seconds * 1000, 2),
            },
        )

        return response
