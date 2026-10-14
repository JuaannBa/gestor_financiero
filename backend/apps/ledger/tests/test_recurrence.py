from datetime import date

import pytest
from dateutil.relativedelta import relativedelta
from django.core.management import call_command
from django.utils import timezone

from ..factories import RecurrenceFactory
from ..models import Transaction
from ..recurrence import advance_date

pytestmark = pytest.mark.django_db


def test_advance_date_monthly_handles_short_months():
    assert advance_date(date(2026, 1, 31), "monthly", 1) == date(2026, 2, 28)
    assert advance_date(date(2026, 3, 15), "yearly", 1) == date(2027, 3, 15)
    assert advance_date(date(2026, 1, 1), "weekly", 2) == date(2026, 1, 15)
    assert advance_date(date(2026, 1, 1), "daily", 3) == date(2026, 1, 4)


def test_generate_recurring_materializes_and_advances(user):
    first_of_month = timezone.localdate().replace(day=1)
    due_from = first_of_month - relativedelta(months=2)
    rec = RecurrenceFactory(
        user=user,
        next_date=due_from,
        frequency="monthly",
        amount="12.99",
        payee="Netflix",
    )

    call_command("generate_recurring")

    txs = Transaction.objects.filter(user=user)
    # due_from, +1 month, +2 months (current month's 1st)
    assert txs.count() == 3
    assert list(txs.order_by("date").values_list("date", flat=True)) == [
        due_from,
        due_from + relativedelta(months=1),
        due_from + relativedelta(months=2),
    ]
    rec.refresh_from_db()
    assert rec.next_date == first_of_month + relativedelta(months=1)
    assert all(t.payee == "Netflix" and t.amount == rec.amount for t in txs)


def test_generate_recurring_skips_inactive_and_future(user):
    first_of_month = timezone.localdate().replace(day=1)
    RecurrenceFactory(
        user=user, next_date=first_of_month - relativedelta(months=1), is_active=False
    )
    RecurrenceFactory(
        user=user,
        next_date=first_of_month + relativedelta(months=3),
        is_active=True,
    )

    call_command("generate_recurring")
    assert Transaction.objects.count() == 0
