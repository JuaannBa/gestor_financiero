from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.queries import DECIMAL, total_balance
from apps.budgets.models import Budget
from apps.ledger.models import Transaction

ZERO = Value(0, output_field=DECIMAL)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        try:
            year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            return Response({"detail": "Invalid year or month"}, status=400)
        if not 1 <= month <= 12:
            return Response({"detail": "Invalid month"}, status=400)

        txs = Transaction.objects.filter(user=request.user, date__year=year, date__month=month)
        totals = txs.aggregate(
            income=Coalesce(Sum("amount", filter=Q(type="income")), ZERO, output_field=DECIMAL),
            expense=Coalesce(Sum("amount", filter=Q(type="expense")), ZERO, output_field=DECIMAL),
        )
        by_category = (
            txs.filter(type="expense", category__isnull=False)
            .values("category_id", "category__name")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )
        budgets = Budget.objects.filter(user=request.user, year=year, month=month).annotate(
            spent=Coalesce(
                Sum(
                    "category__transactions__amount",
                    filter=Q(
                        category__transactions__type="expense",
                        category__transactions__user=request.user,
                        category__transactions__date__year=year,
                        category__transactions__date__month=month,
                    ),
                ),
                Value(0),
                output_field=DECIMAL,
            )
        )
        budget_rows = [
            {
                "id": b.id,
                "category_id": b.category_id,
                "category_name": b.category.name,
                "limit": str(b.amount),
                "spent": str(b.spent),
                "remaining": str(b.amount - b.spent),
                "percent_used": round(float(b.spent / b.amount) * 100, 1) if b.amount else 0,
            }
            for b in budgets.select_related("category")
        ]

        return Response(
            {
                "period": {"year": year, "month": month},
                "net_balance": str(total_balance(request.user)),
                "income": str(totals["income"]),
                "expense": str(totals["expense"]),
                "by_category": [
                    {
                        "category_id": row["category_id"],
                        "category_name": row["category__name"],
                        "total": str(row["total"]),
                    }
                    for row in by_category
                ],
                "budgets": budget_rows,
            }
        )


class BalancesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            months = int(request.query_params.get("months", 12))
        except ValueError:
            return Response({"detail": "Invalid months"}, status=400)
        months = max(1, min(months, 36))

        today = timezone.localdate()
        start = today.replace(day=1) - relativedelta(months=months - 1)

        rows = (
            Transaction.objects.filter(user=request.user, date__gte=start)
            .values("date__year", "date__month")
            .annotate(
                income=Coalesce(Sum("amount", filter=Q(type="income")), ZERO, output_field=DECIMAL),
                expense=Coalesce(
                    Sum("amount", filter=Q(type="expense")), ZERO, output_field=DECIMAL
                ),
                transfer_in=Coalesce(
                    Sum("amount", filter=Q(type="transfer", to_account__user=request.user)),
                    ZERO,
                    output_field=DECIMAL,
                ),
                transfer_out=Coalesce(
                    Sum(
                        "amount",
                        filter=Q(type="transfer", from_account__user=request.user),
                    ),
                    ZERO,
                    output_field=DECIMAL,
                ),
            )
        )
        per_month = {(r["date__year"], r["date__month"]): r for r in rows}

        running = sum(
            (a.opening_balance for a in request.user.accounts.all()),
            start=Decimal("0"),
        )
        series = []
        cursor = start
        for _ in range(months):
            key = (cursor.year, cursor.month)
            r = per_month.get(key)
            if r:
                running = (
                    running + r["income"] - r["expense"] + r["transfer_in"] - r["transfer_out"]
                )
            series.append(
                {"period": f"{cursor.year}-{cursor.month:02d}", "net_balance": str(running)}
            )
            cursor = cursor + relativedelta(months=1)
        return Response({"series": series})
