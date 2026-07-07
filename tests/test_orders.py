# test_orders.py

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from decimal import Decimal
from db_model import OrderStatus, PaymentStatus

from api.orders import router
from api.auth import get_current_user, admin_required
from database import get_db
from tests.conftest import override_get_db


# ------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------

app = FastAPI()
app.include_router(router)

client = TestClient(app)


# Shared fixtures (mock_db, current_user, admin_user, cart) live in tests/conftest.py


# ------------------------------------------------------------------
# User Orders
# ------------------------------------------------------------------

def test_get_user_orders_success(mock_db, current_user):
    fake_orders = [
        {
            "id": 1,
            "user_id": current_user.id,
            "status": OrderStatus.PENDING,
            "total_amount": Decimal("10.00"),
            "payment_status": PaymentStatus.PENDING,
            "created_at": datetime.utcnow(),
        },
        {
            "id": 2,
            "user_id": current_user.id,
            "status": OrderStatus.PENDING,
            "total_amount": Decimal("20.00"),
            "payment_status": PaymentStatus.PENDING,
            "created_at": datetime.utcnow(),
        },
    ]

    query = MagicMock()
    mock_db.query.return_value.filter.return_value = query

    query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = fake_orders
    query.count.return_value = 2

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2
    assert data["page"] == 1
    assert data["size"] == 20
    assert data["total_pages"] == 1
    assert data["has_previous"] is False
    assert data["has_next"] is False



def test_get_user_orders_empty(mock_db, current_user):
    query = MagicMock()
    mock_db.query.return_value.filter.return_value = query

    query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    query.count.return_value = 0

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 0
    assert data["orders"] == []
    assert data["total_pages"] == 0



def test_get_user_orders_database_error(mock_db, current_user):
    query = MagicMock()
    mock_db.query.return_value.filter.return_value = query

    query.order_by.side_effect = SQLAlchemyError()

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.get("/")

    assert response.status_code == 500
    assert response.json()["detail"] == "An error occurred while fetching data from the database."



def test_get_user_orders_unexpected_error(mock_db, current_user):
    mock_db.query.side_effect = Exception()

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.get("/")

    assert response.status_code == 500
    assert response.json()["detail"] == "An unexpected error occurred."



# ------------------------------------------------------------------
# Admin Orders
# ------------------------------------------------------------------

def test_get_all_orders_success(mock_db, admin_user):
    fake_orders = [MagicMock(), MagicMock(), MagicMock()]

    query = MagicMock()
    mock_db.query.return_value = query

    query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = fake_orders
    query.count.return_value = 3

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    response = client.get("/admin")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert data["page"] == 1
    assert data["size"] == 20
    assert data["total_pages"] == 1



def test_get_all_orders_database_error(mock_db, admin_user):
    query = MagicMock()
    mock_db.query.return_value = query

    query.order_by.side_effect = SQLAlchemyError()

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    response = client.get("/admin")

    assert response.status_code == 500
    assert response.json()["detail"] == "An error occurred while fetching data from the database."



def test_get_all_orders_unexpected_error(mock_db, admin_user):
    mock_db.query.side_effect = Exception()

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    response = client.get("/admin")

    assert response.status_code == 500
    assert response.json()["detail"] == "An unexpected error occurred."
