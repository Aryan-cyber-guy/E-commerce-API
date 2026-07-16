# test_products.py

import json
import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from api.products import router
from api.auth import admin_required
from database import get_db
from tests.conftest import override_get_db

app = FastAPI()
app.include_router(router)

client = TestClient(app)


# Shared fixtures (mock_db, current_user, admin_user, cart) live in tests/conftest.py


# ------------------------------------------------------------------
# GET ALL PRODUCTS
# ------------------------------------------------------------------


@patch("api.products.redis_client")
@patch("api.products.ProductResponse")
def test_get_all_products(mock_response, mock_redis, mock_db):
    product = MagicMock()

    query = MagicMock()
    mock_db.query.return_value.filter.return_value = query

    query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
        product
    ]
    query.count.return_value = 1

    dumped = {
        "id": 1,
        "name": "Laptop",
        "description": "Gaming laptop",
        "price": 50000,
        "category": "electronics",
        "stock_quantity": 5,
        "image_url": None,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    mock_response.model_validate.return_value.model_dump.return_value = dumped

    mock_redis.get.return_value = None

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["products"][0]["name"] == "Laptop"

    mock_redis.setex.assert_called_once()


@patch("api.products.redis_client")
def test_get_all_products_from_cache(mock_redis):

    cached = {
        "total": 1,
        "page": 1,
        "size": 20,
        "total_pages": 1,
        "has_previous": False,
        "has_next": False,
        "products": [],
    }

    mock_redis.get.return_value = json.dumps(cached)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["total"] == 1


# ------------------------------------------------------------------
# GET PRODUCT
# ------------------------------------------------------------------


@patch("api.products.redis_client")
@patch("api.products.ProductResponse")
def test_get_product(mock_response, mock_redis, mock_db):

    product = SimpleNamespace(
        id=1,
        name="Laptop",
        description="Gaming laptop",
        price=50000,
        category="electronics",
        stock_quantity=5,
        image_url=None,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    dumped = {
        "id": 1,
        "name": "Laptop",
        "description": "Gaming laptop",
        "price": 50000,
        "category": "electronics",
        "stock_quantity": 5,
        "image_url": None,
        "is_active": True,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }

    mock_response.model_validate.return_value.model_dump.return_value = dumped

    mock_db.query.return_value.filter.return_value.first.return_value = product

    mock_redis.get.return_value = None

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    response = client.get("/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1

    mock_redis.setex.assert_called_once()


@patch("api.products.redis_client")
def test_get_product_not_found(mock_redis, mock_db):

    mock_redis.get.return_value = None

    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    response = client.get("/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


# ------------------------------------------------------------------
# ADD PRODUCT
# ------------------------------------------------------------------


@patch("api.products.redis_client")
def test_add_product(mock_redis, mock_db, admin_user):

    mock_redis.scan_iter.return_value = []

    def refresh_product(product_obj):
        product_obj.id = 1
        product_obj.created_at = datetime.utcnow()
        product_obj.updated_at = datetime.utcnow()
        product_obj.is_active = True

    mock_db.refresh.side_effect = refresh_product

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    payload = {
        "name": "Laptop",
        "description": "Gaming",
        "price": 50000,
        "stock_quantity": 5,
        "category": "electronics",
    }

    response = client.post("/", json=payload)

    assert response.status_code in (200, 201)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


# ------------------------------------------------------------------
# UPDATE PRODUCT
# ------------------------------------------------------------------


@patch("api.products.redis_client")
def test_update_product(mock_redis, mock_db, admin_user):

    product = SimpleNamespace(
        id=1,
        name="Laptop",
        description="Gaming",
        price=50000,
        category="electronics",
        stock_quantity=5,
        image_url="",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    mock_db.query.return_value.filter.return_value.first.return_value = product

    mock_redis.scan_iter.return_value = []

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    response = client.patch(
        "/1",
        json={"price": 1000},
    )

    assert response.status_code == 200

    mock_db.commit.assert_called_once()


@patch("api.products.redis_client")
def test_update_product_not_found(mock_redis, mock_db, admin_user):

    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    response = client.patch("/1", json={"price": 500})

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


# ------------------------------------------------------------------
# DELETE PRODUCT
# ------------------------------------------------------------------


@patch("api.products.redis_client")
def test_delete_product(mock_redis, mock_db, admin_user):

    product = MagicMock()

    mock_db.query.return_value.filter.return_value.first.return_value = product

    mock_redis.scan_iter.return_value = []

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    response = client.delete("/1")

    assert response.status_code == 200
    assert response.json()["message"] == "Product is deleted"

    assert product.is_active is False

    mock_db.commit.assert_called_once()


@patch("api.products.redis_client")
def test_delete_product_not_found(mock_redis, mock_db, admin_user):

    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    response = client.delete("/1")

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


# ------------------------------------------------------------------
# DATABASE ERROR
# ------------------------------------------------------------------


@patch("api.products.redis_client")
def test_add_product_database_error(mock_redis, mock_db, admin_user):

    mock_db.commit.side_effect = SQLAlchemyError()

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    payload = {
        "name": "Laptop",
        "description": "Gaming",
        "price": 1000,
        "stock_quantity": 5,
        "category": "electronics",
    }

    with pytest.raises(SQLAlchemyError):
        client.post("/", json=payload)

    mock_db.rollback.assert_called_once()
