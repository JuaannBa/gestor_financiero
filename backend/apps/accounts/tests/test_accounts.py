import pytest

from apps.ledger.factories import TransactionFactory
from apps.users.factories import UserFactory

from ..factories import AccountFactory

ACCOUNTS = "/api/v1/accounts/"

pytestmark = pytest.mark.django_db


def test_account_list_is_scoped_to_user(auth_client):
    AccountFactory(user=auth_client.user, name="Mine")
    other = UserFactory()
    AccountFactory(user=other, name="Theirs")

    response = auth_client.get(ACCOUNTS)
    assert response.status_code == 200
    names = [a["name"] for a in response.data["results"]]
    assert names == ["Mine"]


def test_create_account_returns_zero_balance(auth_client):
    response = auth_client.post(
        ACCOUNTS,
        {"name": "Checking", "type": "checking", "opening_balance": "100.00"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["balance"] == "100.00"


def test_duplicate_account_name_rejected(auth_client):
    AccountFactory(user=auth_client.user, name="Joint")
    response = auth_client.post(ACCOUNTS, {"name": "Joint", "type": "checking"}, format="json")
    assert response.status_code == 400


def test_account_balance_reflects_transactions(auth_client):
    account = AccountFactory(user=auth_client.user, opening_balance="100.00")
    other = AccountFactory(user=auth_client.user, name="Other", opening_balance="0.00")
    TransactionFactory(user=auth_client.user, account=account, type="expense", amount="30.00")
    TransactionFactory(user=auth_client.user, account=account, type="income", amount="50.00")
    TransactionFactory(
        user=auth_client.user,
        type="transfer",
        amount="10.00",
        from_account=other,
        to_account=account,
        account=None,
    )

    response = auth_client.get(f"{ACCOUNTS}{account.pk}/")
    assert response.status_code == 200
    assert response.data["balance"] == "130.00"


def test_cannot_access_other_users_account(api_client, user):
    victim = UserFactory()
    account = AccountFactory(user=victim)
    api_client.force_authenticate(user=user)
    assert api_client.get(f"{ACCOUNTS}{account.pk}/").status_code == 404
    assert api_client.delete(f"{ACCOUNTS}{account.pk}/").status_code == 404


def test_archive_filter(auth_client):
    AccountFactory(user=auth_client.user, name="Active", is_archived=False)
    AccountFactory(user=auth_client.user, name="Old", is_archived=True)
    response = auth_client.get(ACCOUNTS, {"is_archived": "true"})
    names = [a["name"] for a in response.data["results"]]
    assert names == ["Old"]
