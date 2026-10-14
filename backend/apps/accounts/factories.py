import factory

from apps.users.factories import UserFactory

from .models import Account


class AccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Account

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Account {n}")
    type = Account.Type.CHECKING
    opening_balance = "0.00"
