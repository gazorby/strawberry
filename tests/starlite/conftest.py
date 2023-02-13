import pytest

from starlite.testing import TestClient
from tests.starlite.app import create_app


@pytest.fixture
def test_client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def test_client_keep_alive():
    app = create_app(keep_alive=True, keep_alive_interval=0.1)
    return TestClient(app)
