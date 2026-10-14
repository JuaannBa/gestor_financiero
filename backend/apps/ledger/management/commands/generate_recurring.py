from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.ledger.models import Recurrence, Transaction

MAX_PER_RECURRENCE = 1000


class Command(BaseCommand):
    help = "Materialize due recurring transactions (run daily via cron)."

    def handle(self, *args, **options):
        today = timezone.localdate()
        created = 0
        due = Recurrence.objects.filter(is_active=True, next_date__lte=today).select_related(
            "account", "category", "user"
        )
        for rec in due:
            iterations = 0
            while rec.next_date <= today and iterations < MAX_PER_RECURRENCE:
                Transaction.objects.create(
                    user=rec.user,
                    account=rec.account,
                    type=rec.type,
                    amount=rec.amount,
                    date=rec.next_date,
                    payee=rec.payee,
                    category=rec.category,
                    notes=rec.notes,
                )
                rec.advance()
                created += 1
                iterations += 1
            rec.save(update_fields=["next_date"])
            if iterations >= MAX_PER_RECURRENCE:
                self.stderr.write(f"Warning: recurrence {rec.pk} hit the {MAX_PER_RECURRENCE} cap")

        self.stdout.write(self.style.SUCCESS(f"Created {created} transactions."))
