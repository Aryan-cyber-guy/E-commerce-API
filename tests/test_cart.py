import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.cart import router
from api.auth import get_current_user
from api.cart import get_current_cart
from database import Base, get_db
from db_model import Category, DbUsers, Products, Carts, CartItems, UserRole

# ---------------------------------------------------------------------
# Test Database
# ---------------------------------------------------------------------

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_cart.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db):

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db

    def override_user():
        return db.query(DbUsers).first()

    def override_cart():
        return db.query(Carts).first()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_current_cart] = override_cart

    return TestClient(app)


@pytest.fixture
def seed_data(db):

    user = DbUsers(
        id=1,
        email="test@test.com",
        password_hash="hashed",
        role=UserRole.USER,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        is_active=True,
    )

    cart = Carts(
        id=1,
        user_id=1,
    )

    product = Products(
        id=1,
        name="Keyboard",
        description="Mechanical keyboard",
        price=1000,
        category=Category.ELECTRONICS,
        stock_quantity=10,
        image_url="image.jpg",
    )

    db.add_all([user, cart, product])
    db.commit()


# ---------------------------------------------------------------------
# GET Cart
# ---------------------------------------------------------------------

def test_get_empty_cart(client, seed_data):

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------
# Add Item
# ---------------------------------------------------------------------

def test_add_item(client, seed_data):

    response = client.post(
        "/items",
        json={
            "product_id": 1,
            "quantity": 2,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["message"] == "Item added to cart"
    assert body["item"]["quantity"] == 2
    assert body["item"]["product_id"] == 1


def test_add_invalid_product(client, seed_data):

    response = client.post(
        "/items",
        json={
            "product_id": 100,
            "quantity": 1,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


def test_add_more_than_stock(client, seed_data):

    response = client.post(
        "/items",
        json={
            "product_id": 1,
            "quantity": 100,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient stock"


# ---------------------------------------------------------------------
# Update Item
# ---------------------------------------------------------------------

def test_update_cart_item(client, db, seed_data):

    item = CartItems(
        id=1,
        cart_id=1,
        product_id=1,
        quantity=2,
    )

    db.add(item)
    db.commit()

    response = client.patch(
        "/items/1",
        json={
            "quantity": 5,
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Item updated"


def test_update_invalid_item(client, seed_data):

    response = client.patch(
        "/items/999",
        json={
            "quantity": 2,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"


def test_update_more_than_stock(client, db, seed_data):

    item = CartItems(
        id=1,
        cart_id=1,
        product_id=1,
        quantity=2,
    )

    db.add(item)
    db.commit()

    response = client.patch(
        "/items/1",
        json={
            "quantity": 50,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient stock"


# ---------------------------------------------------------------------
# Delete Item
# ---------------------------------------------------------------------

def test_delete_cart_item(client, db, seed_data):

    item = CartItems(
        id=1,
        cart_id=1,
        product_id=1,
        quantity=2,
    )

    db.add(item)
    db.commit()

    response = client.delete("/items/1")

    assert response.status_code == 200
    assert response.json()["message"] == "Item removed"


def test_delete_invalid_item(client, seed_data):

    response = client.delete("/items/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"


# ---------------------------------------------------------------------
# Existing Item
# ---------------------------------------------------------------------

def test_add_existing_item_increases_quantity(client, db, seed_data):

    item = CartItems(
        id=1,
        cart_id=1,
        product_id=1,
        quantity=2,
    )

    db.add(item)
    db.commit()

    response = client.post(
        "/items",
        json={
            "product_id": 1,
            "quantity": 3,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["item"]["quantity"] == 5