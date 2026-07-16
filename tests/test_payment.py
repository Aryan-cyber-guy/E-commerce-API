# -------------------------------------------------------------
# CREATE PAYMENT SESSION
# -------------------------------------------------------------

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

from db_model import PaymentStatus
from database import get_db
from main import app
from api.auth import get_current_user
from tests.conftest import override_get_db

client = TestClient(app)


def test_create_payment_success(mock_db, current_user):
    order = MagicMock()
    order.id = 1
    order.total_amount = 500
    order.payment_status = PaymentStatus.PENDING

    mock_db.query.return_value.filter.return_value.first.side_effect = [
        order,  # order lookup
        None,  # existing payment lookup
    ]

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.post("/payments/create-session/1")

    assert response.status_code == 200

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_create_payment_order_not_found(mock_db, current_user):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.post("/payments/create-session/1")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


def test_create_payment_no_pending_order(mock_db, current_user):
    order = MagicMock()
    order.payment_status = PaymentStatus.PAID

    mock_db.query.return_value.filter.return_value.first.return_value = order

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.post("/payments/create-session/1")

    assert response.status_code == 400
    assert response.json()["detail"] == "No pending order"


def test_create_payment_existing_payment(mock_db, current_user):
    order = MagicMock()
    order.id = 1
    order.payment_status = PaymentStatus.PENDING

    existing_payment = MagicMock()
    existing_payment.id = 15

    mock_db.query.return_value.filter.return_value.first.side_effect = [
        order,
        existing_payment,
    ]

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.post("/payments/create-session/1")

    assert response.status_code == 200
    assert response.json()["payment_id"] == 15


def test_create_payment_database_error(mock_db, current_user):
    order = MagicMock()
    order.id = 1
    order.total_amount = 200
    order.payment_status = PaymentStatus.PENDING

    mock_db.query.return_value.filter.return_value.first.side_effect = [
        order,
        None,
    ]

    mock_db.commit.side_effect = SQLAlchemyError()

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    with pytest.raises(SQLAlchemyError):
        client.post("/payments/create-session/1")

    mock_db.rollback.assert_called_once()


# -------------------------------------------------------------
# COMPLETE PAYMENT
# -------------------------------------------------------------


def test_payment_success(mock_db, current_user, cart):
    product = MagicMock()
    product.id = 1
    product.name = "Laptop"
    product.stock_quantity = 10

    item = MagicMock()
    item.product_id = 1
    item.quantity = 2

    order = MagicMock()
    order.user_id = current_user.id
    order.order_items = [item]

    payment = MagicMock()
    payment.id = 5
    payment.order = order
    payment.status = PaymentStatus.PENDING

    cart.cart_items = [MagicMock()]

    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.side_effect = [
        payment,
        product,
    ]

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    with patch("main.get_current_cart", return_value=cart):
        response = client.post("/payments/mock/5/success")

    assert response.status_code == 200

    assert product.stock_quantity == 8

    mock_db.commit.assert_called_once()


def test_payment_not_found(mock_db, current_user, cart):
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = (
        None
    )

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    with patch("main.get_current_cart", return_value=cart):
        response = client.post("/payments/mock/1/success")

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"


def test_payment_order_not_found(mock_db, current_user, cart):
    payment = MagicMock()
    payment.order = None

    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = (
        payment
    )

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    with patch("main.get_current_cart", return_value=cart):
        response = client.post("/payments/mock/1/success")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


def test_payment_already_processed(mock_db, current_user, cart):
    payment = MagicMock()
    payment.status = PaymentStatus.PAID
    payment.order = MagicMock(user_id=current_user.id)

    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = (
        payment
    )

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    with patch("main.get_current_cart", return_value=cart):
        response = client.post("/payments/mock/1/success")

    assert response.status_code == 400
    assert response.json()["detail"] == "Payment already processed"


def test_payment_out_of_stock(mock_db, current_user, cart):
    product = MagicMock()
    product.id = 1
    product.name = "Laptop"
    product.stock_quantity = 1

    item = MagicMock()
    item.product_id = 1
    item.quantity = 2

    order = MagicMock()
    order.user_id = current_user.id
    order.order_items = [item]

    payment = MagicMock()
    payment.status = PaymentStatus.PENDING
    payment.order = order

    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.side_effect = [
        payment,
        product,
    ]

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    with patch("main.get_current_cart", return_value=cart):
        response = client.post("/payments/mock/1/success")

    assert response.status_code == 400
    assert response.json()["detail"] == "Laptop is out of stock."


def test_payment_database_error(mock_db, current_user, cart):
    product = MagicMock()
    product.id = 1
    product.name = "Laptop"
    product.stock_quantity = 5

    item = MagicMock()
    item.product_id = 1
    item.quantity = 2

    order = MagicMock()
    order.user_id = current_user.id
    order.order_items = [item]

    payment = MagicMock()
    payment.status = PaymentStatus.PENDING
    payment.order = order

    cart.cart_items = [MagicMock()]

    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.side_effect = [
        payment,
        product,
    ]

    mock_db.commit.side_effect = SQLAlchemyError()

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    with patch("main.get_current_cart", return_value=cart):
        with pytest.raises(SQLAlchemyError):
            client.post("/payments/mock/1/success")

    mock_db.rollback.assert_called_once()
