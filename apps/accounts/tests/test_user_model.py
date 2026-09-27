from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import User


class UserModelTests(TestCase):
    def test_custom_user_model_is_active(self):
        self.assertIs(get_user_model(), User)
