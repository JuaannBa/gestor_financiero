from django.conf import settings
from django.db import models


class Account(models.Model):
    class Type(models.TextChoices):
        CHECKING = "checking", "Checking"
        SAVINGS = "savings", "Savings"
        CREDIT = "credit", "Credit card"
        CASH = "cash", "Cash"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.CHECKING)
    currency = models.CharField(max_length=3, default="EUR")
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_account_name_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"
