import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from db_model import UserRole
from main import app
from fastapi.testclient import TestClient


# Shared mock DB fixture
@pytest.fixture
def mock_db():
    return MagicMock()


def override_get_db(mock_db):
    def _override():
        yield mock_db

    return _override


# Common test users and cart
@pytest.fixture
def current_user():
    user = MagicMock()
    user.id = 1
    user.email = "test@test.com"
    user.name = "Test User"
    user.password_hash = "hashed_password"
    user.role = UserRole.USER
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    user.is_active = True
    return user


@pytest.fixture
def admin_user():
    user = MagicMock()
    user.id = 2
    user.email = "admin@test.com"
    user.name = "Admin User"
    user.password_hash = "hashed_admin"
    user.role = UserRole.ADMIN
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    user.is_active = True
    return user


@pytest.fixture
def cart():
    cart = MagicMock()
    cart.cart_items = []
    return cart


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)
