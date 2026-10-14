from decimal import Decimal

from django.db.models import DecimalField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.ledger.models import Transaction

DECIMAL = DecimalField(max_digits=14, decimal_places=2)


def _subquery(group_by, **filters):
    return (
        Transaction.objects.filter(**filters)
        .order_by()
        .values(group_by)
        .annotate(total=Sum("amount"))
        .values("total")
    )


def balance_annotations():
    """Per-account balance components as annotations (no N+1)."""
    income = _subquery("account", account_id=OuterRef("pk"), type=Transaction.Type.INCOME)
    expense = _subquery("account", account_id=OuterRef("pk"), type=Transaction.Type.EXPENSE)
    transfer_in = _subquery(
        "to_account", to_account_id=OuterRef("pk"), type=Transaction.Type.TRANSFER
    )
    transfer_out = _subquery(
        "from_account", from_account_id=OuterRef("pk"), type=Transaction.Type.TRANSFER
    )
    return {
        "income_total": Coalesce(
            Subquery(income, output_field=DECIMAL), Value(0), output_field=DECIMAL
        ),
        "expense_total": Coalesce(
            Subquery(expense, output_field=DECIMAL), Value(0), output_field=DECIMAL
        ),
        "transfer_in_total": Coalesce(
            Subquery(transfer_in, output_field=DECIMAL), Value(0), output_field=DECIMAL
        ),
        "transfer_out_total": Coalesce(
            Subquery(transfer_out, output_field=DECIMAL), Value(0), output_field=DECIMAL
        ),
    }


def annotated_balance(account):
    """Running balance for one account instance using its annotations."""
    opening = account.opening_balance
    if not hasattr(account, "income_total"):
        raise ValueError("Account must be annotated with balance_annotations()")
    return (
        opening
        + account.income_total
        - account.expense_total
        + account.transfer_in_total
        - account.transfer_out_total
    )


def compute_balance(account):
    """Balance for a single unannotated account (used on create/update responses)."""
    agg = Transaction.objects.filter(
        Q(account=account) | Q(to_account=account) | Q(from_account=account)
    ).aggregate(
        income=Coalesce(
            Sum("amount", filter=Q(type="income", account=account)),
            Value(0),
            output_field=DECIMAL,
        ),
        expense=Coalesce(
            Sum("amount", filter=Q(type="expense", account=account)),
            Value(0),
            output_field=DECIMAL,
        ),
        transfer_in=Coalesce(
            Sum("amount", filter=Q(type="transfer", to_account=account)),
            Value(0),
            output_field=DECIMAL,
        ),
        transfer_out=Coalesce(
            Sum("amount", filter=Q(type="transfer", from_account=account)),
            Value(0),
            output_field=DECIMAL,
        ),
    )
    return (
        account.opening_balance
        + agg["income"]
        - agg["expense"]
        + agg["transfer_in"]
        - agg["transfer_out"]
    )


def total_balance(user):
    """Net worth: opening balances + income - expense + transfers in - out."""
    opening = sum(
        (a.opening_balance for a in user.accounts.all()),
        start=Decimal("0"),
    )
    txs = Transaction.objects.filter(
        Q(account__user=user) | Q(from_account__user=user) | Q(to_account__user=user)
    )
    agg = txs.aggregate(
        income=Coalesce(
            Sum("amount", filter=Q(type=Transaction.Type.INCOME)),
            Value(0),
            output_field=DECIMAL,
        ),
        expense=Coalesce(
            Sum("amount", filter=Q(type=Transaction.Type.EXPENSE)),
            Value(0),
            output_field=DECIMAL,
        ),
        transfer_in=Coalesce(
            Sum("amount", filter=Q(type=Transaction.Type.TRANSFER, to_account__user=user)),
            Value(0),
            output_field=DECIMAL,
        ),
        transfer_out=Coalesce(
            Sum("amount", filter=Q(type=Transaction.Type.TRANSFER, from_account__user=user)),
            Value(0),
            output_field=DECIMAL,
        ),
    )
    return opening + agg["income"] - agg["expense"] + agg["transfer_in"] - agg["transfer_out"]
