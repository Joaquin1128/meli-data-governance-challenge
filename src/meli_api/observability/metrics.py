from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

# Registro propio (no el default global) para que los tests puedan crear
# instancias limpias sin acumular series de corridas anteriores dentro del
# mismo proceso.
registry = CollectorRegistry()

REQUEST_LATENCY_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Latencia de requests HTTP, en segundos",
    ["method", "path", "status_code"],
    registry=registry,
)

REQUEST_ERRORS_TOTAL = Counter(
    "http_request_errors_total",
    "Cantidad de respuestas HTTP con status >= 400",
    ["method", "path", "status_code"],
    registry=registry,
)

CACHE_OPERATIONS_TOTAL = Counter(
    "cache_operations_total",
    "Operaciones de lectura contra el cache, por resultado (hit/miss)",
    ["operation", "result"],
    registry=registry,
)

# 0=closed (sano), 1=open (Redis caído, todas las llamadas fallan rápido sin ir
# a la red), 2=half-open (probando si Redis ya se recuperó).
CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Estado del circuit breaker: 0=closed, 1=open, 2=half-open",
    ["name"],
    registry=registry,
)

_BREAKER_STATE_VALUES = {"closed": 0, "open": 1, "half-open": 2}


def record_http_request(method: str, path_template: str, status_code: int, duration_seconds: float) -> None:
    labels = {"method": method, "path": path_template, "status_code": str(status_code)}
    REQUEST_LATENCY_SECONDS.labels(**labels).observe(duration_seconds)
    if status_code >= 400:
        REQUEST_ERRORS_TOTAL.labels(**labels).inc()


def record_cache_result(operation: str, hit: bool) -> None:
    CACHE_OPERATIONS_TOTAL.labels(operation=operation, result="hit" if hit else "miss").inc()


def set_circuit_breaker_state(name: str, state_name: str) -> None:
    CIRCUIT_BREAKER_STATE.labels(name=name).set(_BREAKER_STATE_VALUES.get(state_name, -1))


def render_metrics() -> bytes:
    return generate_latest(registry)


__all__ = [
    "CONTENT_TYPE_LATEST",
    "record_http_request",
    "record_cache_result",
    "set_circuit_breaker_state",
    "render_metrics",
]
