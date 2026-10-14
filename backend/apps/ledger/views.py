from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .filters import TransactionFilter
from .models import Category, Recurrence, Transaction
from .serializers import CategorySerializer, RecurrenceSerializer, TransactionSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["kind", "parent"]
    ordering_fields = ["name"]

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user).select_related("parent")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = TransactionFilter
    search_fields = ["payee", "notes"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-date", "-created_at"]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).select_related(
            "account", "category", "from_account", "to_account"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RecurrenceViewSet(viewsets.ModelViewSet):
    serializer_class = RecurrenceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["frequency", "is_active", "type"]

    def get_queryset(self):
        return Recurrence.objects.filter(user=self.request.user).select_related(
            "account", "category"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
