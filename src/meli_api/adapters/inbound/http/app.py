from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from meli_api.adapters.inbound.http.error_handlers import register_error_handlers
from meli_api.adapters.inbound.http.middleware import RequestObservabilityMiddleware
from meli_api.adapters.inbound.http.rate_limit import limiter, rate_limit_exceeded_handler
from meli_api.adapters.inbound.http.routers import health, metrics, products
from meli_api.observability.logging import configure_logging


def create_app() -> FastAPI:
    """Factory de la app: nada de estado global a nivel módulo, para que los
    tests puedan crear instancias frescas e independientes."""
    configure_logging()

    app = FastAPI(
        title="MELI Enriched Products API",
        description=(
            "API de solo lectura sobre las descripciones de productos enriquecidas "
            "por el pipeline offline de extracción (MercadoLibre) y enriquecimiento (Gemini)."
        ),
        version="0.1.0",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(RequestObservabilityMiddleware)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(products.router)

    return app


app = create_app()
