import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.users.factories import UserFactory

from ..factories import CategoryFactory

CATS = "/api/v1/categories/"

pytestmark = pytest.mark.django_db


def test_create_and_nest_category(auth_client):
    parent = CategoryFactory(user=auth_client.user, name="Food", kind="expense")
    response = auth_client.post(
        CATS,
        {"name": "Groceries", "kind": "expense", "parent": parent.pk},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["parent"] == parent.pk

    child = auth_client.get(f"{CATS}{response.data['id']}/").data
    assert child["parent"] == parent.pk


def test_parent_kind_must_match(auth_client):
    parent = CategoryFactory(user=auth_client.user, kind="income")
    response = auth_client.post(
        CATS,
        {"name": "Rent", "kind": "expense", "parent": parent.pk},
        format="json",
    )
    assert response.status_code == 400


def test_cannot_nest_under_other_users_category(auth_client):
    foreign = CategoryFactory(user=UserFactory())
    response = auth_client.post(
        CATS,
        {"name": "Sneaky", "kind": "expense", "parent": foreign.pk},
        format="json",
    )
    assert response.status_code == 400


def test_category_list_scoped(auth_client):
    CategoryFactory(user=auth_client.user, name="Mine")
    CategoryFactory(user=UserFactory(), name="Theirs")
    names = [c["name"] for c in auth_client.get(CATS).data["results"]]
    assert names == ["Mine"]


def test_seed_defaults_creates_tree_for_user():
    user = UserFactory()
    call_command("seed_defaults", "--user", user.email)
    # 8 expense + 4 income top-level categories
    assert user.categories.filter(parent=None).count() == 12
    assert user.categories.filter(parent__isnull=False).count() == 17

    # idempotent
    count_after_first = user.categories.count()
    call_command("seed_defaults", "--user", user.email)
    assert user.categories.count() == count_after_first

    with pytest.raises(CommandError):
        call_command("seed_defaults", "--user", "missing@example.com")


def test_seed_defaults_skips_users_with_categories():
    user = UserFactory()
    CategoryFactory(user=user)
    before = user.categories.count()
    call_command("seed_defaults", "--all")
    # --force not given: existing categories untouched
    assert user.categories.count() == before
