import pytest

from meli_api.application.use_cases.get_product import GetProductById
from meli_api.domain.exceptions import ProductNotFoundError
from tests.unit.fakes import FakeProductRepository, make_product


def test_returns_the_product_when_it_exists():
    repository = FakeProductRepository([make_product(item_id="MLA1")])
    use_case = GetProductById(repository)

    product = use_case.execute("MLA1")

    assert product.item_id == "MLA1"


def test_raises_not_found_when_the_product_does_not_exist():
    repository = FakeProductRepository([])
    use_case = GetProductById(repository)

    with pytest.raises(ProductNotFoundError):
        use_case.execute("MLA-inexistente")
