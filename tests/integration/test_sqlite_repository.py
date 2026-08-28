import pytest

from meli_api.adapters.outbound.persistence.sqlite_repository import (
    SqliteProductRepository,
)
from meli_api.domain.exceptions import RepositoryUnavailableError
from meli_api.domain.product import EnrichmentStatus


def test_get_by_id_maps_an_enriched_row_correctly(seeded_db_path):
    repository = SqliteProductRepository(seeded_db_path)

    product = repository.get_by_id("MLA1")

    assert product is not None
    assert product.name == "Notebook Gamer X"
    assert product.status == EnrichmentStatus.ENRICHED
    assert product.description == "Descripción enriquecida por Gemini."
    assert product.specifications == {"RAM": "16GB"}


def test_get_by_id_falls_back_to_original_description_when_not_enriched(seeded_db_path):
    repository = SqliteProductRepository(seeded_db_path)

    product = repository.get_by_id("MLA3")

    assert product.status == EnrichmentStatus.ERROR
    assert product.description == "original"


def test_get_by_id_returns_none_when_missing(seeded_db_path):
    repository = SqliteProductRepository(seeded_db_path)

    assert repository.get_by_id("MLA-inexistente") is None


def test_list_returns_all_products_by_default(seeded_db_path):
    repository = SqliteProductRepository(seeded_db_path)

    items, total = repository.list(status=None, query=None, limit=20, offset=0)

    assert total == 3
    assert {p.item_id for p in items} == {"MLA1", "MLA2", "MLA3"}


def test_list_filters_by_status(seeded_db_path):
    repository = SqliteProductRepository(seeded_db_path)

    items, total = repository.list(
        status=EnrichmentStatus.ERROR, query=None, limit=20, offset=0
    )

    assert total == 1
    assert items[0].item_id == "MLA3"


def test_list_filters_by_query_case_insensitive(seeded_db_path):
    repository = SqliteProductRepository(seeded_db_path)

    items, total = repository.list(status=None, query="notebook", limit=20, offset=0)

    assert total == 1
    assert items[0].item_id == "MLA1"


def test_list_paginates(seeded_db_path):
    repository = SqliteProductRepository(seeded_db_path)

    items, total = repository.list(status=None, query=None, limit=1, offset=1)

    assert total == 3
    assert len(items) == 1


def test_raises_repository_unavailable_when_db_path_is_invalid(tmp_path):
    unreachable_path = str(tmp_path / "no_existe" / "meli_products.db")
    repository = SqliteProductRepository(unreachable_path)

    with pytest.raises(RepositoryUnavailableError):
        repository.get_by_id("MLA1")
