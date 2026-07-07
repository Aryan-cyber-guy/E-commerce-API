from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from main import app
from database import get_db
from tests.conftest import override_get_db

client = TestClient(app, raise_server_exceptions=False)


# -------------------------------------------------------------
# LOGIN
# -------------------------------------------------------------

@patch("main.redis_client")
@patch("main.create_refresh_token")
@patch("main.create_access_token")
@patch("main.verify_password")
def test_login_success(
    mock_verify,
    mock_access,
    mock_refresh,
    mock_redis,
    mock_db,
):

    user = MagicMock()
    user.id = 1
    user.email = "user@test.com"
    user.name = "User"
    user.password_hash = "hashed"
    user.is_active = True
    user.role = "user"
    user.created_at = "2026-01-01T00:00:00Z"
    user.updated_at = "2026-01-01T00:00:00Z"

    mock_db.query.return_value.filter.return_value.first.return_value = user

    mock_verify.return_value = True
    mock_access.return_value = "access"
    mock_refresh.return_value = "refresh"

    mock_redis.incr.return_value = 1
    mock_redis.ttl.return_value = 60

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    response = client.post(
        "/auth/login",
        data={
            "username": "user@test.com",
            "password": "password123",
        },
    )

    assert response.status_code == 200

    assert response.cookies["access_token"] == "access"
    assert response.cookies["refresh_token"] == "refresh"

    mock_redis.delete.assert_called_once()



@patch("main.redis_client")
def test_login_invalid_email(mock_redis, mock_db):

    mock_db.query.return_value.filter.return_value.first.return_value = None

    mock_redis.incr.return_value = 1

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    response = client.post(
        "/auth/login",
        data={
            "username": "wrong@test.com",
            "password": "password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"



@patch("main.redis_client")
def test_login_disabled_account(mock_redis, mock_db):

    user = MagicMock()
    user.is_active = False

    mock_db.query.return_value.filter.return_value.first.return_value = user

    mock_redis.incr.return_value = 1

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    response = client.post(
        "/auth/login",
        data={
            "username": "user@test.com",
            "password": "password",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Account disabled"



@patch("main.redis_client")
@patch("main.verify_password")
def test_login_wrong_password(mock_verify, mock_redis, mock_db):

    user = MagicMock()
    user.is_active = True
    user.password_hash = "hashed"

    mock_db.query.return_value.filter.return_value.first.return_value = user

    mock_verify.return_value = False

    mock_redis.incr.return_value = 1

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    response = client.post(
        "/auth/login",
        data={
            "username": "user@test.com",
            "password": "wrong",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"



@patch("main.redis_client")
def test_login_rate_limit(mock_redis, mock_db):

    mock_redis.incr.return_value = 11
    mock_redis.ttl.return_value = 55

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    response = client.post(
        "/auth/login",
        data={
            "username": "user@test.com",
            "password": "password",
        },
    )

    assert response.status_code == 429
    assert "Too many login attempts" in response.json()["detail"]



@patch("main.redis_client")
def test_login_redis_failure(mock_redis, mock_db):

    user = MagicMock()
    user.id = 1
    user.email = "user@test.com"
    user.name = "User"
    user.password_hash = "hashed"
    user.is_active = True
    user.role = "user"
    user.created_at = "2026-01-01T00:00:00Z"
    user.updated_at = "2026-01-01T00:00:00Z"

    mock_db.query.return_value.filter.return_value.first.return_value = user

    mock_redis.incr.side_effect = RedisError()

    with patch("main.verify_password", return_value=True), \
         patch("main.create_access_token", return_value="access"), \
         patch("main.create_refresh_token", return_value="refresh"):

        app.dependency_overrides[get_db] = override_get_db(mock_db)

        response = client.post(
            "/auth/login",
            data={
                "username": "user@test.com",
                "password": "password",
            },
        )

        assert response.status_code == 200




# -------------------------------------------------------------
# REFRESH TOKEN
# -------------------------------------------------------------

@patch("main.redis_client")
@patch("main.create_refresh_token")
@patch("main.create_access_token")
@patch("main.verify_token")
def test_refresh_success(
    mock_verify,
    mock_access,
    mock_refresh,
    mock_redis,
    mock_db,
):

    user = MagicMock()
    user.id = 1
    user.is_active = True

    mock_db.query.return_value.filter.return_value.first.return_value = user

    mock_verify.return_value = {
        "sub": "1",
        "exp": 9999999999,
    }

    mock_access.return_value = "new_access"
    mock_refresh.return_value = "new_refresh"

    response = client.post(
        "/auth/refresh",
        cookies={"refresh_token": "token"},
    )

    assert response.status_code == 200
    assert response.cookies["access_token"] == "new_access"
    assert response.cookies["refresh_token"] == "new_refresh"


def test_refresh_missing_cookie():

    response = client.post("/auth/refresh")

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token missing"


@patch("main.verify_token")
def test_refresh_invalid_token(mock_verify):

    mock_verify.return_value = {}

    response = client.post(
        "/auth/refresh",
        cookies={"refresh_token": "bad"},
    )

    assert response.status_code == 401


@patch("main.redis_client")
@patch("main.verify_token")
def test_refresh_redis_error(mock_verify, mock_redis, mock_db):

    user = MagicMock()
    user.id = 1
    user.is_active = True

    mock_db.query.return_value.filter.return_value.first.return_value = user

    mock_verify.return_value = {
        "sub": "1",
        "exp": 9999999999,
    }

    mock_redis.setex.side_effect = RedisError()

    app.dependency_overrides[get_db] = override_get_db(mock_db)

    response = client.post(
        "/auth/refresh",
        cookies={"refresh_token": "token"},
    )

    assert response.status_code == 503



# -------------------------------------------------------------
# LOGOUT
# -------------------------------------------------------------

@patch("main.redis_client")
@patch("main.verify_token")
def test_logout_success(mock_verify, mock_redis):

    mock_verify.return_value = {
        "exp": 9999999999,
    }

    response = client.post(
        "/auth/logout",
        cookies={"refresh_token": "token"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out"


def test_logout_missing_cookie():

    response = client.post("/auth/logout")

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token missing"


@patch("main.redis_client")
@patch("main.verify_token")
def test_logout_redis_error(mock_verify, mock_redis):

    mock_verify.return_value = {
        "exp": 9999999999,
    }

    mock_redis.setex.side_effect = RedisError()

    response = client.post(
        "/auth/logout",
        cookies={"refresh_token": "token"},
    )

    assert response.status_code == 503