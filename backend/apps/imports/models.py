from django.db import models


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        PARSED = "parsed", "Parsed"
        COMMITTED = "committed", "Committed"

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="import_batches",
    )
    file_name = models.CharField(max_length=255)
    content = models.TextField()
    columns = models.JSONField(default=list)
    sample_rows = models.JSONField(default=list)
    has_header = models.BooleanField(default=True)
    delimiter = models.CharField(max_length=4, default=",")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PARSED)
    mapping = models.JSONField(null=True, blank=True)
    created_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.file_name} ({self.user.email})"
