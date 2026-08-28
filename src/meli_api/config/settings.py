from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la API vía variables de entorno (prefijo MELI_API_).

    Todo lo que sea "cómo se conecta a algo" o "un umbral operativo" vive acá, no
    hardcodeado en los adapters, para poder ajustarlo sin tocar código.
    """

    model_config = SettingsConfigDict(env_prefix="MELI_API_", env_file=".env")

    db_path: str = "meli_products.db"

    # "redis": cache-aside real, con circuit breaker si Redis se cae.
    # "none": cache deshabilitado a propósito (NullCache) -- no confundir con
    # Redis caído, que se maneja solo con el circuit breaker, sin cambiar esto.
    cache_backend: Literal["redis", "none"] = "redis"
    # "127.0.0.1" en vez de "localhost" a propósito: si Redis está caído, resolver
    # "localhost" prueba primero ::1 (IPv6) y después 127.0.0.1, duplicando el
    # timeout de conexión en cada intento fallido (se midió: ~2s en vez de ~1s
    # por llamada). Con la IP literal se evita esa resolución dual.
    redis_url: str = "redis://127.0.0.1:6379/0"
    cache_ttl_detail_seconds: int = 300
    cache_ttl_list_seconds: int = 60
    redis_breaker_fail_max: int = 5
    redis_breaker_reset_timeout_seconds: int = 30

    # Límite por IP para los endpoints de negocio (/products, /products/{id}).
    # /health y /metrics quedan sin límite: los necesita el propio monitoreo.
    # A esta escala de prototipo alcanza con un limitador en memoria por proceso;
    # en múltiples instancias reales esto se resolvería en el API Gateway
    # (ver docs/architecture.md, sección 6).
    rate_limit_per_minute: int = 60


@lru_cache
def get_settings() -> Settings:
    """Cacheada: las variables de entorno no cambian durante la vida del proceso,
    así que no tiene sentido releerlas/reconstruir el modelo en cada request."""
    return Settings()
