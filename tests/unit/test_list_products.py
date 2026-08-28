import pytest

from meli_api.application.use_cases.list_products import ListProducts
from meli_api.domain.exceptions import InvalidFilterError
from meli_api.domain.product import EnrichmentStatus
from tests.unit.fakes import FakeProductRepository, make_product


def _repository_with(*, enriched: int, error: int) -> FakeProductRepository:
    products = [
        make_product(item_id=f"ENR{i}", status=EnrichmentStatus.ENRICHED)
        for i in range(enriched)
    ] + [
        make_product(item_id=f"ERR{i}", status=EnrichmentStatus.ERROR)
        for i in range(error)
    ]
    return FakeProductRepository(products)


def test_lists_all_products_with_default_pagination():
    repository = _repository_with(enriched=3, error=2)
    use_case = ListProducts(repository)

    page = use_case.execute()

    assert page.total == 5
    assert len(page.items) == 5


def test_filters_by_status():
    repository = _repository_with(enriched=3, error=2)
    use_case = ListProducts(repository)

    page = use_case.execute(status=EnrichmentStatus.ERROR)

    assert page.total == 2
    assert all(p.status == EnrichmentStatus.ERROR for p in page.items)


def test_filters_by_query_on_name():
    repository = FakeProductRepository(
        [make_product(item_id="MLA1", name="Notebook Gamer"), make_product(item_id="MLA2", name="Mouse")]
    )
    use_case = ListProducts(repository)

    page = use_case.execute(query="notebook")

    assert page.total == 1
    assert page.items[0].item_id == "MLA1"


def test_paginates_results():
    repository = _repository_with(enriched=5, error=0)
    use_case = ListProducts(repository)

    page = use_case.execute(limit=2, offset=2)

    assert page.total == 5
    assert len(page.items) == 2
    assert page.limit == 2
    assert page.offset == 2


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_rejects_invalid_limit(limit):
    use_case = ListProducts(FakeProductRepository([]))

    with pytest.raises(InvalidFilterError):
        use_case.execute(limit=limit)


def test_rejects_negative_offset():
    use_case = ListProducts(FakeProductRepository([]))

    with pytest.raises(InvalidFilterError):
        use_case.execute(offset=-1)
