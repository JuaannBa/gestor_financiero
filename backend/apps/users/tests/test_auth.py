import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.users.factories import UserFactory

REGISTER = "/api/v1/auth/register/"
LOGIN = "/api/v1/auth/login/"
REFRESH = "/api/v1/auth/refresh/"
LOGOUT = "/api/v1/auth/logout/"
ME = "/api/v1/auth/me/"

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()


def register(client, email="ana@example.com", password="s3cure-Passw0rd!"):
    return client.post(REGISTER, {"email": email, "password": password}, format="json")


def test_register_creates_user_and_returns_tokens(api_client):
    response = register(api_client)
    assert response.status_code == 201
    assert response.data["email"] == "ana@example.com"
    assert "access" in response.data
    assert "refresh" in response.data

    from apps.users.models import User

    user = User.objects.get(email="ana@example.com")
    assert user.check_password("s3cure-Passw0rd!")
    assert user.has_usable_password()


def test_register_rejects_duplicate_email(api_client):
    register(api_client)
    response = register(api_client)
    assert response.status_code == 400


def test_register_rejects_short_password(api_client):
    response = register(api_client, password="short")
    assert response.status_code == 400


def test_login_with_email_returns_tokens(api_client):
    UserFactory(email="bo@example.com", password="s3cure-Passw0rd!")
    response = api_client.post(
        LOGIN, {"email": "bo@example.com", "password": "s3cure-Passw0rd!"}, format="json"
    )
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


def test_login_wrong_password_rejected(api_client):
    UserFactory(email="bo@example.com", password="s3cure-Passw0rd!")
    response = api_client.post(
        LOGIN, {"email": "bo@example.com", "password": "wrong-password"}, format="json"
    )
    assert response.status_code == 401


def test_me_requires_authentication(api_client):
    assert api_client.get(ME).status_code == 401


def test_me_returns_own_user_only(api_client):
    user_a = UserFactory(email="a@example.com")
    UserFactory(email="b@example.com")
    api_client.force_authenticate(user=user_a)
    response = api_client.get(ME)
    assert response.status_code == 200
    assert response.data["email"] == "a@example.com"


def test_refresh_rotates_and_blacklists_old_token(api_client):
    UserFactory(email="c@example.com", password="s3cure-Passw0rd!")
    login = api_client.post(
        LOGIN, {"email": "c@example.com", "password": "s3cure-Passw0rd!"}, format="json"
    )
    old_refresh = login.data["refresh"]

    rotated = api_client.post(REFRESH, {"refresh": old_refresh}, format="json")
    assert rotated.status_code == 200
    new_refresh = rotated.data["refresh"]
    assert new_refresh != old_refresh

    reuse = api_client.post(REFRESH, {"refresh": old_refresh}, format="json")
    assert reuse.status_code == 401


def test_logout_blacklists_refresh_token(api_client):
    UserFactory(email="d@example.com", password="s3cure-Passw0rd!")
    login = api_client.post(
        LOGIN, {"email": "d@example.com", "password": "s3cure-Passw0rd!"}, format="json"
    )
    refresh = login.data["refresh"]

    logout = api_client.post(LOGOUT, {"refresh": refresh}, format="json")
    assert logout.status_code == 204

    reuse = api_client.post(REFRESH, {"refresh": refresh}, format="json")
    assert reuse.status_code == 401


def test_logout_without_refresh_rejected(api_client):
    assert api_client.post(LOGOUT, {}, format="json").status_code == 400


def test_auth_endpoints_throttled(api_client):
    for _ in range(11):
        response = api_client.post(
            LOGIN, {"email": "x@example.com", "password": "nope"}, format="json"
        )
        if response.status_code == 429:
            break
    assert response.status_code == 429
