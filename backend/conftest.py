import pytest
from rest_framework.test import APIClient

from apps.users.factories import UserFactory


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    client.user = user
    return client
