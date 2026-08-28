from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la API vía variables de entorno (prefijo MELI_API_).

    Todo lo que sea "cómo se conecta a algo" o "un umbral operativo" vive acá, no
    hardcodeado en los adapters, para poder ajustarlo sin tocar código.
    """

    model_config = SettingsConfigDict(env_prefix="MELI_API_", env_file=".env")

    db_path: str = "meli_products.db"

    # Se usan recién en la Parte 5 (cache Redis), ya declaradas para no tener que
    # volver a tocar settings en esa parte.
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_detail_seconds: int = 300
    cache_ttl_list_seconds: int = 60
    redis_breaker_fail_max: int = 5
    redis_breaker_reset_timeout_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    """Cacheada: las variables de entorno no cambian durante la vida del proceso,
    así que no tiene sentido releerlas/reconstruir el modelo en cada request."""
    return Settings()
