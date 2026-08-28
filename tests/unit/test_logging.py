import json
import logging

from meli_api.observability.logging import JsonFormatter


def _make_record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="meli_api.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="algo pasó",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formats_a_plain_record_as_valid_json_with_the_core_fields():
    formatted = JsonFormatter().format(_make_record())
    payload = json.loads(formatted)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "meli_api.test"
    assert payload["message"] == "algo pasó"
    assert "timestamp" in payload


def test_promotes_known_structured_fields_to_the_top_level():
    formatted = JsonFormatter().format(
        _make_record(request_id="abc-123", method="GET", path="/products/{item_id}", status_code=200, duration_ms=12.5)
    )
    payload = json.loads(formatted)

    assert payload["request_id"] == "abc-123"
    assert payload["method"] == "GET"
    assert payload["path"] == "/products/{item_id}"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 12.5


def test_ignores_fields_that_were_not_attached_to_the_record():
    formatted = JsonFormatter().format(_make_record())
    payload = json.loads(formatted)

    assert "request_id" not in payload
    assert "status_code" not in payload
