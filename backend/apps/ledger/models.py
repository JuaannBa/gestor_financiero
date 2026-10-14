from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .recurrence import advance_date


class Category(models.Model):
    class Kind(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    icon = models.CharField(max_length=40, blank=True)
    color = models.CharField(max_length=7, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Transaction(models.Model):
    class Type(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"
        TRANSFER = "transfer", "Transfer"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    # income/expense: account set, from/to null; transfer: from/to set, account null
    account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    type = models.CharField(max_length=10, choices=Type.choices)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    date = models.DateField(db_index=True)
    payee = models.CharField(max_length=150, blank=True)
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    notes = models.TextField(blank=True)

    # transfers
    from_account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transfers_out",
    )
    to_account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transfers_in",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["user", "type", "date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="transaction_amount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        type="transfer",
                        account__isnull=True,
                        from_account__isnull=False,
                        to_account__isnull=False,
                    )
                    | Q(
                        type__in=["income", "expense"],
                        account__isnull=False,
                        from_account__isnull=True,
                        to_account__isnull=True,
                    )
                ),
                name="transaction_type_shape",
            ),
            models.CheckConstraint(
                condition=~Q(from_account=F("to_account")),
                name="transfer_distinct_accounts",
            ),
        ]

    def __str__(self):
        return f"{self.get_type_display()} {self.amount} on {self.date}"


class Recurrence(models.Model):
    """Template that generates income/expense transactions on a schedule."""

    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurrences",
    )
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    interval = models.PositiveIntegerField(default=1)
    next_date = models.DateField()
    is_active = models.BooleanField(default=True)

    # template payload (income/expense only — no transfers)
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        related_name="recurrences",
    )
    type = models.CharField(
        max_length=10,
        choices=[c for c in Transaction.Type.choices if c[0] != "transfer"],
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payee = models.CharField(max_length=150, blank=True)
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recurrences",
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["next_date"]

    def __str__(self):
        return f"{self.get_frequency_display()} {self.type} {self.amount} from {self.next_date}"

    def advance(self):
        """Move next_date forward by one period; deactivate if far in the past overrun."""
        self.next_date = advance_date(self.next_date, self.frequency, self.interval)

    @property
    def due(self):
        return self.is_active and self.next_date <= timezone.localdate()
