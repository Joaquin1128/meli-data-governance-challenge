from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from meli_api.config.settings import get_settings

# Limitador por IP, en memoria del proceso. Suficiente para el prototipo
# (ver docs/architecture.md, sección 6): en múltiples instancias reales esto
# viviría en el API Gateway/API Manager central, no en cada servicio.
limiter = Limiter(key_func=get_remote_address)


def default_rate_limit() -> str:
    """String que entiende slowapi (ej. '60/minute'), leído de Settings.

    Se resuelve en cada request (no una sola vez a nivel módulo) para que un
    override de `get_settings` en tests tenga efecto inmediato.
    """
    return f"{get_settings().rate_limit_per_minute}/minute"


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Mismo formato de error que el resto de la API (ver error_handlers.py),
    en vez del texto plano que devuelve slowapi por default."""
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Límite de requests excedido: {exc.detail}. Reintentá más tarde.",
            }
        },
    )
