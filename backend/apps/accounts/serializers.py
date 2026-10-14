from rest_framework import serializers

from .models import Account
from .queries import annotated_balance, compute_balance


class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            "id",
            "name",
            "type",
            "currency",
            "opening_balance",
            "is_archived",
            "balance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_balance(self, obj):
        value = annotated_balance(obj) if hasattr(obj, "income_total") else compute_balance(obj)
        return f"{value:.2f}"

    def validate_name(self, value):
        user = self.context["request"].user
        qs = Account.objects.filter(user=user, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("You already have an account with this name.")
        return value
