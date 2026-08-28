from meli_api.adapters.outbound.cache.null_cache import NullCache
from meli_api.adapters.outbound.cache.redis_cache import RedisCache
from meli_api.observability.metrics import CIRCUIT_BREAKER_STATE

# Puerto casi con certeza sin nada escuchando: fuerza fallas de conexión
# deterministas sin depender de si la máquina donde corren los tests tiene un
# Redis real levantado en el puerto por default.
_UNREACHABLE_REDIS_URL = "redis://127.0.0.1:1/0"


def _unreachable_cache(fail_max: int = 2) -> RedisCache:
    return RedisCache(
        _UNREACHABLE_REDIS_URL,
        breaker_fail_max=fail_max,
        breaker_reset_timeout_seconds=30,
        socket_timeout_seconds=0.2,
    )


def test_get_returns_none_instead_of_raising_when_redis_is_unreachable():
    cache = _unreachable_cache()

    assert cache.get("product:MLA1") is None


def test_set_and_invalidate_do_not_raise_when_redis_is_unreachable():
    cache = _unreachable_cache()

    cache.set("product:MLA1", "{}", ttl_seconds=60)
    cache.invalidate("product:MLA1")  # No debe lanzar.


def test_status_is_unavailable_when_redis_is_unreachable():
    cache = _unreachable_cache()

    assert cache.status() == "unavailable"


def test_circuit_breaker_opens_after_fail_max_consecutive_failures():
    cache = _unreachable_cache(fail_max=2)

    cache.get("k1")
    cache.get("k2")

    assert cache._breaker.current_state == "open"
    # Con el breaker abierto, una llamada más no debería ni intentar la red
    # (pybreaker corta antes) y debe seguir comportándose como miss.
    assert cache.get("k3") is None


def test_circuit_breaker_state_gauge_reflects_open_after_tripping():
    cache = _unreachable_cache(fail_max=2)
    gauge_value = lambda: CIRCUIT_BREAKER_STATE.labels(name="redis")._value.get()

    assert gauge_value() == 0  # closed al construir

    cache.get("k1")
    cache.get("k2")

    assert gauge_value() == 1  # open


def test_null_cache_is_always_a_miss_and_reports_not_configured():
    cache = NullCache()

    cache.set("k", "v", ttl_seconds=60)

    assert cache.get("k") is None
    assert cache.status() == "not_configured"
