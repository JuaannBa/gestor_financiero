from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.ledger.models import Category


class Budget(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="budgets",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="budgets",
    )
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["year", "month", "category__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category", "year", "month"],
                name="unique_budget_per_category_month",
            ),
            models.CheckConstraint(
                condition=models.Q(month__gte=1, month__lte=12),
                name="budget_month_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="budget_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.category.name} {self.year}-{self.month:02d}: {self.amount}"
