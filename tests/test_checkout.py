# -------------------------------------------------------------
# CHECKOUT
# -------------------------------------------------------------

from decimal import Decimal
from unittest.mock import MagicMock
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

from main import app
from database import get_db
from tests.conftest import override_get_db
from api.auth import get_current_user
from api.cart import get_current_cart

client = TestClient(app, raise_server_exceptions=False)

# Use shared `cart` fixture from tests/conftest.py


def test_checkout_success(mock_db, current_user, cart):
    product = MagicMock()
    product.stock_quantity = 10
    product.price = Decimal("100.00")

    cart_item = MagicMock()
    cart_item.product = product
    cart_item.quantity = 2

    cart.cart_items = [cart_item]

    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_current_cart] = lambda: cart

    response = client.post("/checkout")

    assert response.status_code == 200

    data = response.json()

    assert float(data["total_amount"]) == 200.0

    mock_db.add.assert_called()
    mock_db.flush.assert_called_once()
    mock_db.commit.assert_called_once()


def test_checkout_empty_cart(mock_db, current_user, cart):
    cart.cart_items = []
    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_current_cart] = lambda: cart

    response = client.post("/checkout")

    assert response.status_code == 400
    assert response.json()["detail"] == "Cart is empty"


def test_checkout_insufficient_stock(mock_db, current_user, cart):
    product = MagicMock()
    product.stock_quantity = 1
    product.price = Decimal("100")

    item = MagicMock()
    item.product = product
    item.quantity = 5

    cart.cart_items = [item]
    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_current_cart] = lambda: cart

    response = client.post("/checkout")

    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient stock"


def test_checkout_pending_order_exists(mock_db, current_user, cart):
    product = MagicMock()
    product.stock_quantity = 10
    product.price = Decimal("50")

    item = MagicMock()
    item.product = product
    item.quantity = 2

    cart.cart_items = [item]

    pending = MagicMock()

    mock_db.query.return_value.filter.return_value.first.return_value = pending

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_current_cart] = lambda: cart

    response = client.post("/checkout")

    assert response.status_code == 400
    assert response.json()["detail"] == "Complete your existing order first."


def test_checkout_database_error(mock_db, current_user, cart):
    product = MagicMock()
    product.stock_quantity = 10
    product.price = Decimal("100")

    item = MagicMock()
    item.product = product
    item.quantity = 1

    cart.cart_items = [item]

    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.commit.side_effect = SQLAlchemyError()

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_current_cart] = lambda: cart

    response = client.post("/checkout")
    assert response.status_code == 500

    mock_db.rollback.assert_called_once()
