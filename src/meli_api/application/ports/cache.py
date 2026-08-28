from typing import Protocol


class Cache(Protocol):
    """Puerto de cache, deliberadamente 'tonto' (strings ya serializados).

    Así el use case nunca necesita saber si el adapter detrás es Redis, un
    `NullCache` no-op (Redis no configurado) o cualquier otra cosa: un miss se ve
    igual que "Redis está caído" que "no había nada cacheado".
    """

    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...

    def invalidate(self, key: str) -> None: ...
