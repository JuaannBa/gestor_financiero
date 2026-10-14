from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import Account

from .models import Category, Recurrence, Transaction

User = get_user_model()


def owned(model, value, user, field_name):
    if value is None:
        return value
    if not model.objects.filter(pk=value.pk, user=user).exists():
        raise serializers.ValidationError({field_name: "Not found."})
    return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "parent", "name", "kind", "icon", "color", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_parent(self, value):
        if value is None:
            return value
        user = self.context["request"].user
        owned(Category, value, user, "parent")
        if self.instance and value.pk == self.instance.pk:
            raise serializers.ValidationError({"parent": "A category cannot be its own parent."})
        if value.kind != (
            self.initial_data.get("kind") or (self.instance.kind if self.instance else None)
        ):
            raise serializers.ValidationError({"parent": "Parent must have the same kind."})
        return value


class TransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    from_account_name = serializers.SerializerMethodField()
    to_account_name = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "type",
            "amount",
            "date",
            "payee",
            "notes",
            "account",
            "category",
            "from_account",
            "to_account",
            "account_name",
            "category_name",
            "from_account_name",
            "to_account_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    @staticmethod
    def get_account_name(obj):
        return obj.account.name if obj.account else None

    @staticmethod
    def get_category_name(obj):
        return obj.category.name if obj.category else None

    @staticmethod
    def get_from_account_name(obj):
        return obj.from_account.name if obj.from_account else None

    @staticmethod
    def get_to_account_name(obj):
        return obj.to_account.name if obj.to_account else None

    def validate_account(self, value):
        return owned(Account, value, self.context["request"].user, "account")

    def validate_from_account(self, value):
        return owned(Account, value, self.context["request"].user, "from_account")

    def validate_to_account(self, value):
        return owned(Account, value, self.context["request"].user, "to_account")

    def validate_category(self, value):
        return owned(Category, value, self.context["request"].user, "category")

    def validate(self, attrs):
        instance = self.instance
        request = self.context["request"]

        t = attrs.get("type", instance.type if instance else None)
        account = attrs.get("account", instance.account if instance else None)
        from_account = attrs.get("from_account", instance.from_account if instance else None)
        to_account = attrs.get("to_account", instance.to_account if instance else None)
        category = attrs.get("category", instance.category if instance else None)

        if t == "transfer":
            attrs["account"] = None
            attrs["category"] = None
            if not from_account or not to_account:
                raise serializers.ValidationError(
                    {"to_account": "Transfers require from_account and to_account."}
                )
            if from_account.pk == to_account.pk:
                raise serializers.ValidationError(
                    {"to_account": "Transfer accounts must be different."}
                )
            for acc in (from_account, to_account):
                if acc.user_id != request.user.pk:
                    raise serializers.ValidationError(
                        {"from_account": "Accounts must belong to you."}
                    )
        else:
            attrs["from_account"] = None
            attrs["to_account"] = None
            if not account:
                raise serializers.ValidationError(
                    {"account": f"{t.capitalize()} requires an account."}
                )
            if category is not None and category.kind != t:
                raise serializers.ValidationError(
                    {"category": f"Category kind '{category.kind}' does not match type '{t}'."}
                )

        return attrs


class RecurrenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recurrence
        fields = [
            "id",
            "frequency",
            "interval",
            "next_date",
            "is_active",
            "account",
            "type",
            "amount",
            "payee",
            "category",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_account(self, value):
        return owned(Account, value, self.context["request"].user, "account")

    def validate_category(self, value):
        if value is None:
            return value
        owned(Category, value, self.context["request"].user, "category")
        if value.kind != self.initial_data.get("type", getattr(self.instance, "type", None)):
            raise serializers.ValidationError(
                {"category": "Category kind does not match recurrence type."}
            )
        return value
