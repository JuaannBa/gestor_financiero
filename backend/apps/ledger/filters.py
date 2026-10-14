import django_filters
from django.db.models import Q

from .models import Transaction


class TransactionFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    account = django_filters.NumberFilter(method="filter_account")

    class Meta:
        model = Transaction
        fields = ["type", "category", "date_from", "date_to", "account"]

    def filter_account(self, queryset, name, value):
        return queryset.filter(Q(account=value) | Q(from_account=value) | Q(to_account=value))
