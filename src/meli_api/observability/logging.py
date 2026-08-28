import json
import logging
import sys

# Campos que un log de acceso o de negocio puede adjuntar vía `extra={...}` y
# que, si están presentes, se promueven a nivel raíz del JSON (en vez de quedar
# enterrados en `record.__dict__`). En un entorno real esto se ingestaría en
# CloudWatch/Datadog/ELK y se indexaría por estos mismos campos.
_STRUCTURED_FIELDS = (
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Reemplaza los handlers del root logger por uno solo, a stdout, en JSON.

    Se llama una vez al arrancar la app (ver `app.py`). Todos los `logger =
    logging.getLogger(...)` del resto del código (adapters, use cases) heredan
    esta configuración sin tener que tocarla individualmente.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn arma su propio access log en texto plano con handlers propios,
    # independientes del root logger -- quedaría duplicando en un formato
    # distinto lo que `RequestObservabilityMiddleware` ya loguea en JSON con
    # más contexto (request_id, duration_ms). Se desactiva para no ensuciar
    # la salida con dos formatos de log mezclados.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False
