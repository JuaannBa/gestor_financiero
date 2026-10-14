from rest_framework import serializers

from .models import Budget


class BudgetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    spent = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, default=0)

    class Meta:
        model = Budget
        fields = [
            "id",
            "category",
            "category_name",
            "year",
            "month",
            "amount",
            "spent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "spent", "created_at", "updated_at"]

    def validate_category(self, value):
        user = self.context["request"].user
        if value.user_id != user.pk:
            raise serializers.ValidationError("Not found.")
        if value.kind != "expense":
            raise serializers.ValidationError("Budgets require an expense category.")
        return value

    def validate_year(self, value):
        if not 2000 <= value <= 2100:
            raise serializers.ValidationError("Year must be between 2000 and 2100.")
        return value

    def validate_month(self, value):
        if not 1 <= value <= 12:
            raise serializers.ValidationError("Month must be between 1 and 12.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        qs = Budget.objects.filter(
            user=user,
            category=attrs.get("category"),
            year=attrs.get("year"),
            month=attrs.get("month"),
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A budget for this category, year and month already exists."
            )
        return attrs
