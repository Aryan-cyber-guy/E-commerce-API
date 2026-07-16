# -------------------------------------------------------------
# ADMIN - Toggle User Status
# -------------------------------------------------------------

import pytest
from unittest.mock import MagicMock
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient


from api.auth import admin_required
from main import app
from database import get_db
from tests.conftest import override_get_db

client = TestClient(app)

# Use shared `admin_user` fixture from tests/conftest.py


def test_toggle_user_status_success(mock_db, admin_user):
    target_user = MagicMock()
    target_user.id = 3
    target_user.is_active = True

    mock_db.query.return_value.filter.return_value.first.return_value = target_user

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    response = client.patch("/admin/users/2/status")

    assert response.status_code == 200
    assert response.json()["message"] == "User disabled"
    assert target_user.is_active is False

    mock_db.commit.assert_called_once()


def test_toggle_user_status_enable(mock_db, admin_user):
    target_user = MagicMock()
    target_user.id = 3
    target_user.is_active = False

    mock_db.query.return_value.filter.return_value.first.return_value = target_user

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    response = client.patch("/admin/users/2/status")

    assert response.status_code == 200
    assert response.json()["message"] == "User enabled"
    assert target_user.is_active is True


def test_toggle_user_status_user_not_found(mock_db, admin_user):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    response = client.patch("/admin/users/999/status")

    assert response.status_code == 404
    assert response.json()["detail"] == "No user found"


def test_toggle_user_status_self_disable(mock_db, admin_user):
    mock_db.query.return_value.filter.return_value.first.return_value = admin_user

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    response = client.patch(f"/admin/users/{admin_user.id}/status")

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot disable your own account"


def test_toggle_user_status_database_error(mock_db, admin_user):
    target_user = MagicMock()
    target_user.id = 3
    target_user.is_active = True

    mock_db.query.return_value.filter.return_value.first.return_value = target_user
    mock_db.commit.side_effect = SQLAlchemyError()

    app.dependency_overrides[get_db] = override_get_db(mock_db)
    app.dependency_overrides[admin_required] = lambda: admin_user

    with pytest.raises(SQLAlchemyError):
        client.patch("/admin/users/2/status")

    mock_db.rollback.assert_called_once()
