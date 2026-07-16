import pytest
from fastapi import HTTPException
from jose import jwt

from api.auth import (
    SECRET_KEY,
    ALGORITHM,
    hash_password,
    verify_password,
    verify_token,
    create_access_token,
    create_refresh_token,
    get_current_user,
    admin_required,
)
from db_model import UserRole

# -------------------------------------------------------------------
# Password hashing
# -------------------------------------------------------------------


def test_hash_password_returns_different_string():
    password = "mypassword123"

    hashed = hash_password(password)

    assert hashed != password
    assert isinstance(hashed, str)


def test_verify_password_success():
    password = "mypassword123"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_failure():
    hashed = hash_password("mypassword123")

    assert verify_password("wrongpassword", hashed) is False


# -------------------------------------------------------------------
# Token creation
# -------------------------------------------------------------------


def test_create_access_token():
    token = create_access_token(5)

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == "5"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_create_refresh_token():
    token = create_refresh_token(10)

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == "10"
    assert payload["type"] == "refresh"
    assert "exp" in payload


# -------------------------------------------------------------------
# verify_token
# -------------------------------------------------------------------


def test_verify_access_token():
    token = create_access_token(1)

    payload = verify_token(token, "access")

    assert payload["sub"] == "1"
    assert payload["type"] == "access"


def test_verify_refresh_token(monkeypatch):
    token = create_refresh_token(1)

    class FakeRedis:
        def get(self, key):
            return None

    monkeypatch.setattr("api.auth.redis_client", FakeRedis())

    payload = verify_token(token, "refresh")

    assert payload["sub"] == "1"
    assert payload["type"] == "refresh"


def test_verify_invalid_token():
    with pytest.raises(HTTPException) as exc:
        verify_token("this-is-not-a-token", "access")

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"


def test_verify_wrong_token_type():
    token = create_access_token(1)

    with pytest.raises(HTTPException) as exc:
        verify_token(token, "refresh")

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token type"


def test_verify_blacklisted_refresh_token(monkeypatch):
    token = create_refresh_token(1)

    class FakeRedis:
        def get(self, key):
            return "blacklisted"

    monkeypatch.setattr("api.auth.redis_client", FakeRedis())

    with pytest.raises(HTTPException) as exc:
        verify_token(token, "refresh")

    assert exc.value.status_code == 401
    assert exc.value.detail == "Blacklisted token"


# -------------------------------------------------------------------
# get_current_user
# -------------------------------------------------------------------


class FakeRequest:
    def __init__(self, token):
        self.cookies = {"access_token": token}


class FakeUser:
    def __init__(self, id=1, active=True):
        self.id = id
        self.is_active = active
        self.role = UserRole.USER


class FakeQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.user


class FakeDB:
    def __init__(self, user):
        self.user = user

    def query(self, model):
        return FakeQuery(self.user)


def test_get_current_user_success():
    token = create_access_token(1)
    request = FakeRequest(token)
    db = FakeDB(FakeUser())

    user = get_current_user(request, db)

    assert user.id == 1


def test_get_current_user_missing_cookie():
    class Request:
        cookies = {}

    with pytest.raises(HTTPException) as exc:
        get_current_user(Request(), FakeDB(FakeUser()))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Access token missing"


def test_get_current_user_invalid_user():
    token = create_access_token(1)
    request = FakeRequest(token)

    with pytest.raises(HTTPException) as exc:
        get_current_user(request, FakeDB(None))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid User ID"


def test_get_current_user_disabled():
    token = create_access_token(1)
    request = FakeRequest(token)

    with pytest.raises(HTTPException) as exc:
        get_current_user(request, FakeDB(FakeUser(active=False)))

    assert exc.value.status_code == 403
    assert exc.value.detail == "Account disabled"


# -------------------------------------------------------------------
# admin_required
# -------------------------------------------------------------------


def test_admin_required_success():
    user = FakeUser()
    user.role = UserRole.ADMIN

    assert admin_required(user) == user


def test_admin_required_failure():
    user = FakeUser()
    user.role = UserRole.USER

    with pytest.raises(HTTPException) as exc:
        admin_required(user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Admin access required"
