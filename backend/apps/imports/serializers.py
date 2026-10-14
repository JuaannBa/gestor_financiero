from rest_framework import serializers

from apps.accounts.models import Account

from .models import ImportBatch

MAX_CONTENT_CHARS = 2_000_000


class ImportBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportBatch
        fields = [
            "id",
            "file_name",
            "columns",
            "sample_rows",
            "has_header",
            "delimiter",
            "status",
            "mapping",
            "created_count",
            "skipped_count",
            "created_at",
        ]
        read_only_fields = fields


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    has_header = serializers.BooleanField(required=False)

    def validate_file(self, value):
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("File too large (max 2 MB)")
        raw = value.read()
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw.decode("latin-1")
        if len(content) > MAX_CONTENT_CHARS:
            raise serializers.ValidationError("File too large (max 2 MB)")
        return {"name": value.name, "content": content}


class ColumnField(serializers.Field):
    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, str)):
            raise serializers.ValidationError("Column must be an index or header name")
        return data

    def to_representation(self, value):
        return value


class MappingSerializer(serializers.Serializer):
    account = serializers.IntegerField()
    date = ColumnField()
    amount = ColumnField()
    payee = ColumnField(required=False, allow_null=True, default=None)
    category = ColumnField(required=False, allow_null=True, default=None)
    type = ColumnField(required=False, allow_null=True, default=None)
    notes = ColumnField(required=False, allow_null=True, default=None)
    date_format = serializers.CharField(required=False)

    def validate_account(self, value):
        if not Account.objects.filter(pk=value, user=self.context["request"].user).exists():
            raise serializers.ValidationError("Account not found.")
        return value
