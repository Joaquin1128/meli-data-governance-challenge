class NullCache:
    """Implementación no-op del puerto `Cache`.

    Se usa cuando el cache está deliberadamente deshabilitado
    (`MELI_API_CACHE_BACKEND=none`) -- no cuando Redis está caído, para eso ya
    está `RedisCache` con su propio manejo de fallas. Con esto, la API funciona
    igual de bien sin ningún Redis configurado, solo que sin acelerar lecturas
    repetidas.
    """

    def get(self, key: str) -> str | None:
        return None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        return None

    def invalidate(self, key: str) -> None:
        return None

    def status(self) -> str:
        return "not_configured"
