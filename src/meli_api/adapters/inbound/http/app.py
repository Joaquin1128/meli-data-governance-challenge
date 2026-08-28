from fastapi import FastAPI

from meli_api.adapters.inbound.http.error_handlers import register_error_handlers
from meli_api.adapters.inbound.http.routers import health, products


def create_app() -> FastAPI:
    """Factory de la app: nada de estado global a nivel módulo, para que los
    tests puedan crear instancias frescas e independientes."""
    app = FastAPI(
        title="MELI Enriched Products API",
        description=(
            "API de solo lectura sobre las descripciones de productos enriquecidas "
            "por el pipeline offline de extracción (MercadoLibre) y enriquecimiento (Gemini)."
        ),
        version="0.1.0",
    )

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(products.router)

    return app


app = create_app()
