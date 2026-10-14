import factory
from django.utils import timezone

from apps.accounts.factories import AccountFactory
from apps.users.factories import UserFactory

from .models import Category, Recurrence, Transaction


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Category {n}")
    kind = Category.Kind.EXPENSE


class TransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Transaction

    user = factory.SubFactory(UserFactory)
    account = factory.SubFactory(AccountFactory)
    type = Transaction.Type.EXPENSE
    amount = "10.00"
    date = factory.LazyFunction(timezone.localdate)
    payee = factory.Sequence(lambda n: f"Payee {n}")


class RecurrenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Recurrence

    user = factory.SubFactory(UserFactory)
    account = factory.SubFactory(AccountFactory)
    type = Transaction.Type.EXPENSE
    frequency = Recurrence.Frequency.MONTHLY
    interval = 1
    next_date = factory.LazyFunction(timezone.localdate)
    amount = "50.00"
