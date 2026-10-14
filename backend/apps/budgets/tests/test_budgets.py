from datetime import date

import pytest

from apps.accounts.factories import AccountFactory
from apps.ledger.factories import CategoryFactory, TransactionFactory
from apps.users.factories import UserFactory

from ..factories import BudgetFactory

BUDGETS = "/api/v1/budgets/"

pytestmark = pytest.mark.django_db


def test_create_budget(auth_client):
    cat = CategoryFactory(user=auth_client.user, kind="expense")
    response = auth_client.post(
        BUDGETS,
        {"category": cat.pk, "year": 2026, "month": 3, "amount": "400.00"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["spent"] == "0.00"


def test_duplicate_budget_rejected(auth_client):
    cat = CategoryFactory(user=auth_client.user, kind="expense")
    payload = {"category": cat.pk, "year": 2026, "month": 3, "amount": "400.00"}
    assert auth_client.post(BUDGETS, payload, format="json").status_code == 201
    assert auth_client.post(BUDGETS, payload, format="json").status_code == 400


def test_budget_requires_expense_category(auth_client):
    income_cat = CategoryFactory(user=auth_client.user, kind="income")
    response = auth_client.post(
        BUDGETS,
        {"category": income_cat.pk, "year": 2026, "month": 1, "amount": "100.00"},
        format="json",
    )
    assert response.status_code == 400


def test_invalid_month_rejected(auth_client):
    cat = CategoryFactory(user=auth_client.user, kind="expense")
    response = auth_client.post(
        BUDGETS,
        {"category": cat.pk, "year": 2026, "month": 13, "amount": "100.00"},
        format="json",
    )
    assert response.status_code == 400


def test_cannot_use_other_users_category(auth_client):
    foreign = CategoryFactory(user=UserFactory(), kind="expense")
    response = auth_client.post(
        BUDGETS,
        {"category": foreign.pk, "year": 2026, "month": 5, "amount": "50.00"},
        format="json",
    )
    assert response.status_code == 400


def test_spent_only_counts_requested_period(auth_client):
    cat = CategoryFactory(user=auth_client.user, kind="expense", name="Food")
    BudgetFactory(user=auth_client.user, category=cat, year=2026, month=1, amount="200.00")
    account = AccountFactory(user=auth_client.user)
    TransactionFactory(
        user=auth_client.user,
        account=account,
        category=cat,
        type="expense",
        amount="30.00",
        date=date(2026, 1, 10),
    )
    TransactionFactory(
        user=auth_client.user,
        account=account,
        category=cat,
        type="expense",
        amount="70.00",
        date=date(2026, 2, 10),
    )

    response = auth_client.get(BUDGETS, {"year": 2026, "month": 1})
    assert response.data["count"] == 1
    row = response.data["results"][0]
    assert row["spent"] == "30.00"
    assert row["amount"] == "200.00"


def test_budget_scoped_to_user(api_client, user):
    budget = BudgetFactory(user=UserFactory())
    api_client.force_authenticate(user=user)
    assert api_client.get(f"{BUDGETS}{budget.pk}/").status_code == 404
