from datetime import date

import pytest
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.accounts.factories import AccountFactory
from apps.budgets.factories import BudgetFactory
from apps.ledger.factories import CategoryFactory, TransactionFactory

DASH = "/api/v1/reports/dashboard/"
BALANCES = "/api/v1/reports/balances/"

pytestmark = pytest.mark.django_db


def test_dashboard_aggregates(auth_client):
    user = auth_client.user
    account = AccountFactory(user=user, opening_balance="1000.00")
    salary_cat = CategoryFactory(user=user, kind="income", name="Salary")
    rent_cat = CategoryFactory(user=user, kind="expense", name="Rent")
    food_cat = CategoryFactory(user=user, kind="expense", name="Food")

    TransactionFactory(
        user=user,
        account=account,
        type="income",
        amount="3000.00",
        category=salary_cat,
        date=date(2026, 1, 5),
    )
    TransactionFactory(
        user=user,
        account=account,
        type="expense",
        amount="100.00",
        category=rent_cat,
        date=date(2026, 1, 6),
    )
    TransactionFactory(
        user=user,
        account=account,
        type="expense",
        amount="50.00",
        category=food_cat,
        date=date(2026, 1, 7),
    )
    # February expense must NOT leak into January
    TransactionFactory(
        user=user,
        account=account,
        type="expense",
        amount="999.00",
        date=date(2026, 2, 7),
    )
    BudgetFactory(user=user, category=food_cat, year=2026, month=1, amount="200.00")

    response = auth_client.get(DASH, {"year": 2026, "month": 1})
    assert response.status_code == 200
    data = response.json()

    assert data["income"] == "3000.00"
    assert data["expense"] == "150.00"
    # net worth = opening 1000 + income 3000 - Jan expenses 150 - Feb expense 999
    assert data["net_balance"] == "2851.00"

    by_cat = {row["category_name"]: row["total"] for row in data["by_category"]}
    assert by_cat == {"Rent": "100.00", "Food": "50.00"}

    (budget,) = data["budgets"]
    assert budget["category_name"] == "Food"
    assert budget["spent"] == "50.00"
    assert budget["remaining"] == "150.00"
    assert budget["percent_used"] == 25.0


def test_dashboard_rejects_bad_period(auth_client):
    assert auth_client.get(DASH, {"year": 2026, "month": 13}).status_code == 400
    assert auth_client.get(DASH, {"year": "abc", "month": 1}).status_code == 400


def test_dashboard_requires_auth(api_client):
    assert api_client.get(DASH).status_code == 401


def test_balance_series(auth_client):
    user = auth_client.user
    account = AccountFactory(user=user, opening_balance="500.00")
    today = timezone.localdate()
    this_month = today.replace(day=1)
    two_months_ago = this_month - relativedelta(months=2)
    one_month_ago = this_month - relativedelta(months=1)

    TransactionFactory(
        user=user,
        account=account,
        type="income",
        amount="200.00",
        date=two_months_ago.replace(day=3),
    )
    TransactionFactory(
        user=user,
        account=account,
        type="expense",
        amount="100.00",
        date=one_month_ago.replace(day=3),
    )

    response = auth_client.get(BALANCES, {"months": 3})
    assert response.status_code == 200
    series = response.json()["series"]
    assert len(series) == 3

    expected_final = "600.00"  # 500 opening + 200 income - 100 expense
    assert series[-1]["net_balance"] == expected_final
    # periods are chronological monthly
    periods = [row["period"] for row in series]
    assert periods[0] == f"{two_months_ago.year}-{two_months_ago.month:02d}"
    assert periods[-1] == f"{this_month.year}-{this_month.month:02d}"
