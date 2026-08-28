def test_get_product_by_id_returns_enriched_description(client):
    response = client.get("/products/MLA1")

    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == "MLA1"
    assert body["enrichment_status"] == "enriched"
    assert body["description"] == "Descripción enriquecida por Gemini."
    assert body["specifications"] == {"RAM": "16GB"}


def test_get_product_falls_back_to_original_description(client):
    response = client.get("/products/MLA3")

    assert response.status_code == 200
    body = response.json()
    assert body["enrichment_status"] == "error"
    assert body["description"] == "original"


def test_get_product_not_found_returns_404_with_descriptive_body(client):
    response = client.get("/products/MLA-inexistente")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "PRODUCT_NOT_FOUND"


def test_list_products_default_pagination(client):
    response = client.get("/products")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["limit"] == 20
    assert body["offset"] == 0


def test_list_products_filters_by_status(client):
    response = client.get("/products", params={"status": "error"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["item_id"] == "MLA3"


def test_list_products_filters_by_query(client):
    response = client.get("/products", params={"q": "notebook"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["item_id"] == "MLA1"


def test_list_products_invalid_status_returns_422(client):
    response = client.get("/products", params={"status": "not-a-real-status"})

    assert response.status_code == 422


def test_list_products_limit_out_of_range_returns_422(client):
    response = client.get("/products", params={"limit": 0})

    assert response.status_code == 422


def test_health_reports_ok_when_database_is_reachable(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
