from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.factories import AccountFactory
from apps.ledger.factories import CategoryFactory
from apps.users.factories import UserFactory

from ..models import ImportBatch
from ..parsers import parse_amount, parse_date

IMPORTS = "/api/v1/imports/"

pytestmark = pytest.mark.django_db

BANK_CSV = (
    "Datum;Beschreibung;Kategorie;Betrag\n"
    "01/10/2026;Supermarket;Groceries;-45,20\n"
    "02/10/2026;Salary;;2.500,00\n"
    "03/10/2026;Cafe;Restaurants;-3,50\n"
)


def upload(client, content=BANK_CSV, name="bank.csv", has_header=True):
    file = SimpleUploadedFile(name, content.encode(), content_type="text/csv")
    return client.post(IMPORTS, {"file": file, "has_header": has_header}, format="multipart")


def mapping_for(batch, account, **overrides):
    base = {"account": account.pk, "date": 0, "amount": 3, "payee": 1, "category": 2}
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56", Decimal("1234.56")),
        ("1,234.56", Decimal("1234.56")),
        ("12,34", Decimal("12.34")),
        ("12.34", Decimal("12.34")),
        ("1.234", Decimal("1234")),
        ("(12.00)", Decimal("-12.00")),
        ("-5,00", Decimal("-5.00")),
        ("12 EUR", Decimal("12")),
        ("45,20-", Decimal("-45.20")),
    ],
)
def test_parse_amount_formats(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-01-05", date(2026, 1, 5)),
        ("05/01/2026", date(2026, 1, 5)),
        ("05-01-2026", date(2026, 1, 5)),
        ("05.01.2026", date(2026, 1, 5)),
    ],
)
def test_parse_date_formats(raw, expected):
    assert parse_date(raw) == expected


def test_parse_date_invalid():
    with pytest.raises(ValueError):
        parse_date("not-a-date")


def test_upload_detects_semicolon_and_header(auth_client):
    response = upload(auth_client)
    assert response.status_code == 201
    data = response.json()
    assert data["delimiter"] == ";"
    assert data["has_header"] is True
    assert data["columns"] == ["Datum", "Beschreibung", "Kategorie", "Betrag"]
    assert data["status"] == "parsed"


def test_preview_then_commit_creates_transactions(auth_client):
    user = auth_client.user
    account = AccountFactory(user=user, opening_balance="0.00")
    grocer = CategoryFactory(user=user, kind="expense", name="Groceries")
    CategoryFactory(user=user, kind="income", name="Salary")

    batch = upload(auth_client).json()

    preview = auth_client.post(
        f"{IMPORTS}{batch['id']}/preview/", mapping_for(batch, account), format="json"
    )
    assert preview.status_code == 200
    data = preview.json()
    assert data["valid_count"] == 3
    assert data["income_count"] == 1
    assert data["expense_count"] == 2
    assert data["duplicate_count"] == 0
    assert data["errors"] == []

    commit = auth_client.post(
        f"{IMPORTS}{batch['id']}/commit/", mapping_for(batch, account), format="json"
    )
    assert commit.status_code == 200
    assert commit.json() == {"created": 3, "skipped_duplicates": 0, "total": 3}

    from apps.ledger.models import Transaction

    expense = Transaction.objects.get(payee="Supermarket")
    assert expense.type == "expense"
    assert expense.amount == Decimal("45.20")
    assert expense.category == grocer

    income = Transaction.objects.get(payee="Salary")
    assert income.type == "income"
    assert income.amount == Decimal("2500.00")

    # balance: +2500 - 45.20 - 3.50
    assert auth_client.get(f"/api/v1/accounts/{account.pk}/").json()["balance"] == "2451.30"


def test_reimport_skips_duplicates(auth_client):
    account = AccountFactory(user=auth_client.user)
    first_batch = upload(auth_client).json()
    auth_client.post(
        f"{IMPORTS}{first_batch['id']}/commit/", mapping_for(first_batch, account), format="json"
    )

    second_batch = upload(auth_client).json()
    commit = auth_client.post(
        f"{IMPORTS}{second_batch['id']}/commit/", mapping_for(second_batch, account), format="json"
    )
    assert commit.json() == {"created": 0, "skipped_duplicates": 3, "total": 3}

    from apps.ledger.models import Transaction

    assert Transaction.objects.filter(user=auth_client.user).count() == 3


def test_commit_blocked_when_row_errors(auth_client):
    user = auth_client.user
    account = AccountFactory(user=user)
    bad_csv = "date;payee;amount\n01/10/2026;Ok;-10,00\nnot-a-date;Bad;-5,00\n"
    batch = upload(auth_client, content=bad_csv).json()
    mapping = {"account": account.pk, "date": 0, "amount": 2, "payee": 1}

    preview = auth_client.post(f"{IMPORTS}{batch['id']}/preview/", mapping, format="json")
    data = preview.json()
    assert len(data["errors"]) == 1
    assert data["errors"][0]["line"] == 3

    commit = auth_client.post(f"{IMPORTS}{batch['id']}/commit/", mapping, format="json")
    assert commit.status_code == 400


def test_mapping_by_index_without_header(auth_client):
    account = AccountFactory(user=auth_client.user)
    no_header = "01/10/2026;Shop;-10,00\n02/10/2026;Boss;900,00\n"
    batch = upload(auth_client, content=no_header, has_header=False).json()
    assert batch["has_header"] is False

    commit = auth_client.post(
        f"{IMPORTS}{batch['id']}/commit/",
        {"account": account.pk, "date": 0, "payee": 1, "amount": 2},
        format="json",
    )
    assert commit.status_code == 200
    assert commit.json()["created"] == 2


def test_foreign_account_rejected(auth_client):
    batch = upload(auth_client).json()
    foreign = AccountFactory(user=UserFactory())
    response = auth_client.post(
        f"{IMPORTS}{batch['id']}/preview/", mapping_for(batch, foreign), format="json"
    )
    assert response.status_code == 400


def test_batch_scoped_to_user(api_client):
    user = UserFactory()
    batch = ImportBatch.objects.create(
        user=user, file_name="x.csv", content="a", columns=["a"], sample_rows=[]
    )
    client = APIClient()
    client.force_authenticate(user=UserFactory())
    assert client.get(f"{IMPORTS}{batch.pk}/").status_code == 404
    assert client.delete(f"{IMPORTS}{batch.pk}/").status_code == 404
