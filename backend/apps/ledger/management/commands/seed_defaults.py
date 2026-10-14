from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.ledger.models import Category

User = get_user_model()

DEFAULT_TREE = {
    "expense": {
        "Housing": ["Rent", "Utilities", "Internet"],
        "Food": ["Groceries", "Restaurants", "Takeaway"],
        "Transport": ["Fuel", "Public transport", "Car maintenance"],
        "Health": ["Pharmacy", "Doctor"],
        "Shopping": ["Clothes", "Electronics"],
        "Entertainment": ["Subscriptions", "Hobbies"],
        "Education": [],
        "Other": [],
    },
    "income": {
        "Salary": ["Bonus"],
        "Freelance": [],
        "Investments": ["Dividends"],
        "Other income": [],
    },
}


class Command(BaseCommand):
    help = "Create the default category tree for one user (--user) or all users (--all)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Email of the target user")
        parser.add_argument(
            "--all",
            action="store_true",
            dest="all_users",
            help="Apply to every user without categories",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Create even if the user already has categories",
        )

    def handle(self, *args, **options):
        if bool(options["user"]) == bool(options["all_users"]):
            raise CommandError("Provide exactly one of --user or --all")

        if options["user"]:
            try:
                users = [User.objects.get(email__iexact=options["user"])]
            except User.DoesNotExist:
                raise CommandError(f"No user with email {options['user']}") from None
        else:
            users = User.objects.all()

        created_total = 0
        for user in users:
            if user.categories.exists() and not options["force"]:
                self.stdout.write(f"skip {user.email} (has categories)")
                continue
            created = self._seed(user)
            created_total += created
            self.stdout.write(f"{user.email}: +{created} categories")

        self.stdout.write(self.style.SUCCESS(f"Done. {created_total} categories created."))

    def _seed(self, user):
        count = 0
        for kind, parents in DEFAULT_TREE.items():
            for parent_name, children in parents.items():
                parent, _ = Category.objects.get_or_create(
                    user=user, parent=None, name=parent_name, kind=kind
                )
                count += 1
                for child in children:
                    Category.objects.get_or_create(user=user, parent=parent, name=child, kind=kind)
                    count += 1
        return count
