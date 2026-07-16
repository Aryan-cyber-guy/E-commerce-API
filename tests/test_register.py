from datetime import datetime
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from db_model import UserRole
from main import app
from database import get_db
from api.auth import get_current_user
from tests.conftest import override_get_db

client = TestClient(app, raise_server_exceptions=False)


# Shared fixtures (mock_db, current_user, admin_user, cart) live in tests/conftest.py


# -------------------------------------------------------------------
# Health Check
# -------------------------------------------------------------------


def test_health_check():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Server is running"}


# -------------------------------------------------------------------
# Register
# -------------------------------------------------------------------


@patch("main.hash_password")
def test_register_success(mock_hash, mock_db):
    mock_hash.return_value = "hashed_password"

    query = MagicMock()
    mock_db.query.return_value.filter.return_value = query
    query.first.return_value = None

    def refresh_user(user_obj):
        user_obj.id = 1
        user_obj.role = UserRole.USER
        user_obj.created_at = datetime.utcnow()
        user_obj.updated_at = datetime.utcnow()
        user_obj.is_active = True

    mock_db.refresh.side_effect = refresh_user

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    payload = {"email": "user@test.com", "password": "Password123"}

    response = client.post("/auth/register", json=payload)

    assert response.status_code in (200, 201)

    mock_db.add.assert_called()
    assert mock_db.commit.call_count == 2


def test_register_existing_user(mock_db):
    query = MagicMock()
    query.first.return_value = MagicMock()

    mock_db.query.return_value.filter.return_value = query

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    payload = {"email": "user@test.com", "password": "Password123"}

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "User already registered"


@patch("main.hash_password")
def test_register_database_error(mock_hash, mock_db):
    mock_hash.return_value = "hashed"

    query = MagicMock()
    query.first.return_value = None

    mock_db.query.return_value.filter.return_value = query
    mock_db.commit.side_effect = SQLAlchemyError()

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    payload = {"email": "user@test.com", "password": "Password123"}

    response = client.post("/auth/register", json=payload)
    assert response.status_code == 500

    mock_db.rollback.assert_called()


# -------------------------------------------------------------------
# Read Current User
# -------------------------------------------------------------------


def test_get_current_user(current_user):
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["email"] == "test@test.com"


# -------------------------------------------------------------------
# Update User
# -------------------------------------------------------------------


def test_update_user_name(mock_db, current_user):
    query = MagicMock()
    query.first.return_value = None

    mock_db.query.return_value.filter.return_value = query

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.patch(
        "/users/me",
        json={"name": "New Name"},
    )

    assert response.status_code == 200

    assert current_user.name == "New Name"

    mock_db.commit.assert_called_once()


def test_update_user_duplicate_email(mock_db, current_user):
    query = MagicMock()
    query.first.return_value = MagicMock()

    mock_db.query.return_value.filter.return_value = query

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.patch(
        "/users/me",
        json={"email": "existing@test.com"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email is already in use"


def test_update_user_database_error(mock_db, current_user):
    query = MagicMock()
    query.first.return_value = None

    mock_db.query.return_value.filter.return_value = query

    mock_db.commit.side_effect = SQLAlchemyError()

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.patch(
        "/users/me",
        json={"name": "Updated"},
    )

    assert response.status_code == 500
    mock_db.rollback.assert_called_once()


# -------------------------------------------------------------------
# Update Password
# -------------------------------------------------------------------


@patch("main.verify_password")
@patch("main.hash_password")
def test_update_password_success(mock_hash, mock_verify, mock_db, current_user):
    mock_verify.side_effect = [True, False]
    mock_hash.return_value = "new_hash"

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.patch(
        "/users/me/password",
        json={"current_password": "oldpass1", "new_password": "newpass123"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"

    assert current_user.password_hash == "new_hash"

    mock_db.commit.assert_called_once()


@patch("main.verify_password")
def test_update_password_wrong_current_password(mock_verify, mock_db, current_user):
    mock_verify.return_value = False

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.patch(
        "/users/me/password",
        json={"current_password": "wrongpass", "new_password": "newpass12"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"


@patch("main.verify_password")
def test_update_password_same_password(mock_verify, mock_db, current_user):
    mock_verify.side_effect = [True, True]

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.patch(
        "/users/me/password",
        json={"current_password": "password", "new_password": "password"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "New password must be different"


@patch("main.verify_password")
@patch("main.hash_password")
def test_update_password_database_error(mock_hash, mock_verify, mock_db, current_user):
    mock_verify.side_effect = [True, False]
    mock_hash.return_value = "new_hash"

    mock_db.commit.side_effect = SQLAlchemyError()

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[get_current_user] = lambda: current_user

    response = client.patch(
        "/users/me/password",
        json={"current_password": "oldpass1", "new_password": "newpass12"},
    )

    assert response.status_code == 500
    mock_db.rollback.assert_called_once()
