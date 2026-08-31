import logging

import pybreaker
import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from meli_api.observability.metrics import set_circuit_breaker_state

logger = logging.getLogger("meli_api.redis_cache")


class _BreakerStateMetricsListener(pybreaker.CircuitBreakerListener):
    """Publica cada transición de estado del breaker como métrica Gauge, para
    poder graficarlo/alertar en Prometheus (ver docs/architecture.md, sección 5)."""

    def __init__(self, name: str):
        self._name = name

    def state_change(self, cb, old_state, new_state) -> None:
        set_circuit_breaker_state(self._name, new_state.name)
        logger.warning(
            "Circuit breaker %r cambió de estado: %s -> %s",
            self._name,
            old_state.name if old_state else "n/a",
            new_state.name,
        )


class RedisCache:
    """Adapter Redis del puerto `Cache`. Diseñado para que Redis nunca pueda
    tumbar la API: toda falla se traga acá y se traduce en "no había nada
    cacheado" hacia arriba.

    El circuit breaker (pybreaker) es lo que evita que, con Redis caído, cada
    request pague el costo de intentar conectarse y fallar: tras
    `breaker_fail_max` fallos consecutivos el breaker abre y las llamadas
    siguientes fallan instantáneamente (sin tocar la red) durante
    `breaker_reset_timeout_seconds`, momento en el que prueba de nuevo
    (half-open). Sin este breaker, cada endpoint sumaría el timeout de conexión
    de Redis a su latencia mientras el servicio está caído.
    """

    def __init__(
        self,
        redis_url: str,
        breaker_fail_max: int,
        breaker_reset_timeout_seconds: int,
        socket_timeout_seconds: float = 1.0,
    ):
        self._client = redis.Redis.from_url(
            redis_url,
            socket_connect_timeout=socket_timeout_seconds,
            socket_timeout=socket_timeout_seconds,
            # redis-py por default reintenta 10 veces con backoff exponencial+jitter
            # ante ConnectionError/TimeoutError; eso duplicaría la política de
            # reintentos que ya decidimos manejar nosotros vía el circuit breaker,
            # y haría que cada request pague hasta 10x el timeout de conexión
            # mientras Redis está caído. Se desactiva explícitamente acá.
            retry=Retry(NoBackoff(), retries=0),
            retry_on_timeout=False,
            retry_on_error=[],
        )
        self._breaker = pybreaker.CircuitBreaker(
            fail_max=breaker_fail_max,
            reset_timeout=breaker_reset_timeout_seconds,
            listeners=[_BreakerStateMetricsListener("redis")],
        )
        set_circuit_breaker_state("redis", self._breaker.current_state)

    def get(self, key: str) -> str | None:
        try:
            value = self._breaker.call(self._client.get, key)
        except (redis.RedisError, pybreaker.CircuitBreakerError) as exc:
            logger.warning("Redis GET falló para %r (tratado como cache-miss): %s", key, exc)
            return None
        return value.decode("utf-8") if value is not None else None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            self._breaker.call(self._client.set, key, value, ex=ttl_seconds)
        except (redis.RedisError, pybreaker.CircuitBreakerError) as exc:
            logger.warning("Redis SET falló para %r (se ignora, no es crítico): %s", key, exc)

    def invalidate(self, key: str) -> None:
        try:
            self._breaker.call(self._client.delete, key)
        except (redis.RedisError, pybreaker.CircuitBreakerError) as exc:
            logger.warning("Redis DELETE falló para %r (se ignora): %s", key, exc)

    def status(self) -> str:
        if self._breaker.current_state == "open":
            return "unavailable"
        try:
            self._breaker.call(self._client.ping)
        except (redis.RedisError, pybreaker.CircuitBreakerError):
            return "unavailable"
        return "ok"
