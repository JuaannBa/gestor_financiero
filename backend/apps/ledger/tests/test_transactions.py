from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.factories import AccountFactory
from apps.users.factories import UserFactory

from ..factories import CategoryFactory, TransactionFactory

TX = "/api/v1/transactions/"
ACCTS = "/api/v1/accounts/"

pytestmark = pytest.mark.django_db


def today():
    return timezone.localdate()


def test_create_income_and_expense(auth_client):
    account = AccountFactory(user=auth_client.user, opening_balance="0.00")
    cat = CategoryFactory(user=auth_client.user, kind="expense")

    income = auth_client.post(
        TX,
        {
            "type": "income",
            "amount": "2500.00",
            "date": str(today()),
            "account": account.pk,
            "payee": "Employer",
        },
        format="json",
    )
    assert income.status_code == 201

    expense = auth_client.post(
        TX,
        {
            "type": "expense",
            "amount": "42.50",
            "date": str(today()),
            "account": account.pk,
            "category": cat.pk,
        },
        format="json",
    )
    assert expense.status_code == 201
    assert expense.data["category_name"] == cat.name

    balance = auth_client.get(f"{ACCTS}{account.pk}/").data["balance"]
    assert balance == "2457.50"


def test_expense_with_income_category_rejected(auth_client):
    account = AccountFactory(user=auth_client.user)
    income_cat = CategoryFactory(user=auth_client.user, kind="income")
    response = auth_client.post(
        TX,
        {
            "type": "expense",
            "amount": "10.00",
            "date": str(today()),
            "account": account.pk,
            "category": income_cat.pk,
        },
        format="json",
    )
    assert response.status_code == 400
    assert "category" in response.data


def test_income_requires_account(auth_client):
    response = auth_client.post(
        TX,
        {"type": "income", "amount": "10.00", "date": str(today())},
        format="json",
    )
    assert response.status_code == 400
    assert "account" in response.data


def test_transfer_moves_money_between_own_accounts(auth_client):
    a = AccountFactory(user=auth_client.user, opening_balance="1000.00", name="A")
    b = AccountFactory(user=auth_client.user, opening_balance="0.00", name="B")

    response = auth_client.post(
        TX,
        {
            "type": "transfer",
            "amount": "200.00",
            "date": str(today()),
            "from_account": a.pk,
            "to_account": b.pk,
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["from_account_name"] == "A"
    assert response.data["to_account_name"] == "B"

    assert auth_client.get(f"{ACCTS}{a.pk}/").data["balance"] == "800.00"
    assert auth_client.get(f"{ACCTS}{b.pk}/").data["balance"] == "200.00"


def test_transfer_requires_distinct_valid_accounts(auth_client):
    a = AccountFactory(user=auth_client.user)
    # same account
    same = auth_client.post(
        TX,
        {
            "type": "transfer",
            "amount": "10.00",
            "date": str(today()),
            "from_account": a.pk,
            "to_account": a.pk,
        },
        format="json",
    )
    assert same.status_code == 400

    # missing to_account
    missing = auth_client.post(
        TX,
        {"type": "transfer", "amount": "10.00", "date": str(today()), "from_account": a.pk},
        format="json",
    )
    assert missing.status_code == 400


def test_cannot_use_other_users_accounts(auth_client):
    victim = AccountFactory(user=UserFactory())
    response = auth_client.post(
        TX,
        {
            "type": "expense",
            "amount": "10.00",
            "date": str(today()),
            "account": victim.pk,
        },
        format="json",
    )
    assert response.status_code == 400
    assert "account" in response.data


def test_transaction_list_scoped_and_filterable(auth_client):
    account = AccountFactory(user=auth_client.user)
    other_account = AccountFactory(user=UserFactory(), name="Other")

    TransactionFactory(
        user=auth_client.user, account=account, type="expense", amount="10.00", payee="Groceries"
    )
    TransactionFactory(
        user=auth_client.user,
        account=account,
        type="expense",
        amount="99.00",
        payee="Electronics",
        date=today() - timedelta(days=40),
    )
    TransactionFactory(user=UserFactory(), account=other_account, payee="Hidden")

    all_tx = auth_client.get(TX)
    assert all_tx.data["count"] == 2

    by_type = auth_client.get(TX, {"type": "expense"})
    assert by_type.data["count"] == 2

    recent = auth_client.get(TX, {"date_from": str(today() - timedelta(days=7))})
    assert recent.data["count"] == 1
    assert recent.data["results"][0]["payee"] == "Groceries"

    search = auth_client.get(TX, {"search": "Electr"})
    assert search.data["count"] == 1


def test_account_filter_includes_transfer_sides(auth_client):
    a = AccountFactory(user=auth_client.user, name="A")
    b = AccountFactory(user=auth_client.user, name="B")
    TransactionFactory(
        user=auth_client.user,
        type="transfer",
        amount="5.00",
        from_account=a,
        to_account=b,
        account=None,
    )
    TransactionFactory(user=auth_client.user, account=b, type="expense", amount="1.00")

    response = auth_client.get(TX, {"account": a.pk})
    assert response.data["count"] == 1
    assert response.data["results"][0]["type"] == "transfer"

    response_b = auth_client.get(TX, {"account": b.pk})
    assert response_b.data["count"] == 2


def test_update_and_delete_recompute_balance(auth_client):
    account = AccountFactory(user=auth_client.user, opening_balance="100.00")
    tx = TransactionFactory(user=auth_client.user, account=account, amount="10.00")

    patch = auth_client.patch(f"{TX}{tx.pk}/", {"amount": "25.00"}, format="json")
    assert patch.status_code == 200
    assert auth_client.get(f"{ACCTS}{account.pk}/").data["balance"] == "75.00"

    delete = auth_client.delete(f"{TX}{tx.pk}/")
    assert delete.status_code == 204
    assert auth_client.get(f"{ACCTS}{account.pk}/").data["balance"] == "100.00"


def test_cannot_access_other_users_transaction(api_client, user):
    victim_tx = TransactionFactory(user=UserFactory())
    api_client.force_authenticate(user=user)
    assert api_client.get(f"{TX}{victim_tx.pk}/").status_code == 404
