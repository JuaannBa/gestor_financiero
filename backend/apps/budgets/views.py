from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Budget
from .serializers import BudgetSerializer


class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["year", "month", "category"]
    ordering_fields = ["year", "month"]

    def get_queryset(self):
        qs = (
            Budget.objects.filter(user=self.request.user)
            .select_related("category")
            .order_by("year", "month", "category__name")
        )
        year = self.request.query_params.get("year")
        month = self.request.query_params.get("month")
        if year and month and year.isdigit() and month.isdigit():
            year_i, month_i = int(year), int(month)
            qs = qs.filter(year=year_i, month=month_i).annotate(
                spent=Coalesce(
                    Sum(
                        "category__transactions__amount",
                        filter=Q(
                            category__transactions__type="expense",
                            category__transactions__user=self.request.user,
                            category__transactions__date__year=year_i,
                            category__transactions__date__month=month_i,
                        ),
                    ),
                    Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
