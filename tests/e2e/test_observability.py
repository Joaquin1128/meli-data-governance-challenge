def test_metrics_endpoint_exposes_prometheus_text_format(client):
    client.get("/products/MLA1")
    client.get("/products/MLA-inexistente")  # genera un 404, para el contador de errores

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "http_request_duration_seconds" in body
    assert "http_request_errors_total" in body
    assert "cache_operations_total" in body


def test_metrics_use_the_route_template_not_the_concrete_item_id(client):
    client.get("/products/MLA1")

    body = client.get("/metrics").text

    assert 'path="/products/{item_id}"' in body
    assert "MLA1" not in body


def test_every_response_carries_a_request_id_header(client):
    response = client.get("/products/MLA1")

    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0
