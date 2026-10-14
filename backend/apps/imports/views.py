import csv
import io

from django.db import IntegrityError
from django.db import transaction as db_transaction
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.accounts.models import Account
from apps.ledger.models import Category, Transaction

from .models import ImportBatch
from .parsers import fingerprint, parse_csv, parse_row, resolve_column
from .serializers import ImportBatchSerializer, MappingSerializer, UploadSerializer

COLUMN_FIELDS = ["date", "amount", "payee", "category", "type", "notes"]


class ImportBatchViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return UploadSerializer
        return ImportBatchSerializer

    def get_queryset(self):
        return ImportBatch.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file_data = serializer.validated_data["file"]
        try:
            parsed = parse_csv(file_data["content"], serializer.validated_data.get("has_header"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        parsed.pop("total_rows", None)

        batch = ImportBatch.objects.create(
            user=request.user,
            file_name=file_data["name"],
            content=file_data["content"],
            **parsed,
        )
        return Response(
            ImportBatchSerializer(batch).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        batch = self.get_object()
        mapping = self._validated_mapping(batch, request)
        if isinstance(mapping, Response):
            return mapping
        result = self._process(batch, mapping)
        result.pop("_valid")
        return Response(result)

    @action(detail=True, methods=["post"])
    def commit(self, request, pk=None):
        batch = self.get_object()
        mapping = self._validated_mapping(batch, request)
        if isinstance(mapping, Response):
            return mapping

        result = self._process(batch, mapping)
        if result["errors"]:
            return Response({"errors": result["errors"]}, status=status.HTTP_400_BAD_REQUEST)

        valid = result.pop("_valid")
        created, race_skipped = self._persist(valid)
        skipped = result["duplicate_count"] + race_skipped
        batch.status = ImportBatch.Status.COMMITTED
        batch.mapping = mapping
        batch.created_count += created
        batch.skipped_count += skipped
        batch.save(update_fields=["status", "mapping", "created_count", "skipped_count"])
        return Response(
            {
                "created": created,
                "skipped_duplicates": skipped,
                "total": created + skipped,
            }
        )

    def _validated_mapping(self, batch, request):
        serializer = MappingSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        mapping = dict(serializer.validated_data)
        try:
            for field in COLUMN_FIELDS:
                if mapping.get(field) is not None:
                    mapping[field] = resolve_column(mapping[field], batch.columns)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return mapping

    def _data_rows(self, batch):
        rows = [
            r
            for r in csv.reader(io.StringIO(batch.content), delimiter=batch.delimiter)
            if any(cell.strip() for cell in r)
        ]
        if batch.has_header:
            rows = rows[1:]
        return rows

    def _process(self, batch, mapping):
        user = batch.user
        account = Account.objects.get(pk=mapping["account"], user=user)
        rows = self._data_rows(batch)

        existing = set(
            Transaction.objects.filter(user=user, import_fingerprint__isnull=False).values_list(
                "import_fingerprint", flat=True
            )
        )
        seen: set[str] = set()

        errors = []
        valid = []
        income_count = expense_count = duplicate_count = 0

        for i, row in enumerate(rows):
            line = i + (2 if batch.has_header else 1)
            try:
                fields = parse_row(row, mapping, batch.columns, user.pk)
            except ValueError as exc:
                errors.append({"line": line, "message": str(exc)})
                if len(errors) >= 100:
                    errors.append({"line": None, "message": "Too many errors — stopped"})
                    break
                continue

            category = None
            if fields["category_name"] and mapping.get("category") is not None:
                category = (
                    Category.objects.filter(
                        user=user,
                        name__iexact=fields["category_name"],
                        kind=fields["type"],
                    )
                    .order_by("parent_id")
                    .first()
                )

            fp = fingerprint(
                user.pk,
                account.pk,
                fields["date"],
                fields["amount"],
                fields["payee"],
                fields["type"],
            )
            if fp in existing or fp in seen:
                duplicate_count += 1
            else:
                seen.add(fp)
                if fields["type"] == "income":
                    income_count += 1
                else:
                    expense_count += 1
                valid.append(
                    {
                        "date": fields["date"],
                        "amount": fields["amount"],
                        "type": fields["type"],
                        "payee": fields["payee"],
                        "notes": fields["notes"],
                        "category": category,
                        "account": account,
                        "user": user,
                        "import_fingerprint": fp,
                    }
                )

        return {
            "total_rows": len(rows),
            "valid_count": len(valid),
            "income_count": income_count,
            "expense_count": expense_count,
            "duplicate_count": duplicate_count,
            "errors": errors,
            "sample": [
                {
                    "date": str(v["date"]),
                    "amount": str(v["amount"]),
                    "type": v["type"],
                    "payee": v["payee"],
                }
                for v in valid[:10]
            ],
            "_valid": valid,
        }

    def _persist(self, valid):
        skipped = 0
        created = 0
        for chunk_start in range(0, len(valid), 500):
            chunk = valid[chunk_start : chunk_start + 500]
            try:
                with db_transaction.atomic():
                    objs = Transaction.objects.bulk_create(
                        [Transaction(**item) for item in chunk], batch_size=500
                    )
                    created += len(objs)
            except IntegrityError:
                # fingerprint raced with a concurrent import — insert one by one
                for item in chunk:
                    _, was_created = Transaction.objects.get_or_create(
                        user=item["user"],
                        import_fingerprint=item["import_fingerprint"],
                        defaults=item,
                    )
                    if was_created:
                        created += 1
                    else:
                        skipped += 1
        return created, skipped
