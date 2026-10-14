from django.db.models import F
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Account
from .queries import balance_annotations
from .serializers import AccountSerializer


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name"]
    ordering_fields = ["name", "type", "created_at"]
    filterset_fields = ["type", "is_archived"]

    def get_queryset(self):
        return (
            Account.objects.filter(user=self.request.user)
            .annotate(**balance_annotations())
            .annotate(
                balance=(
                    F("opening_balance")
                    + F("income_total")
                    - F("expense_total")
                    + F("transfer_in_total")
                    - F("transfer_out_total")
                )
            )
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)
