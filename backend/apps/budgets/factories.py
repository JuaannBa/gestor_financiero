import factory

from apps.ledger.factories import CategoryFactory
from apps.users.factories import UserFactory

from .models import Budget


class BudgetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Budget

    user = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory)
    year = 2026
    month = 1
    amount = "200.00"
