from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import SabyConnection


class HomePageSabyConnectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="test-user",
            password="test-password",
        )
        self.client.force_login(self.user)

    def test_disconnected_user_sees_connect_button(self):
        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saby пока не подключён.")
        self.assertContains(response, "Подключить Saby")
        self.assertNotContains(response, "Отключить Saby")

    def test_connected_user_sees_disconnect_button(self):
        SabyConnection.objects.create(
            user=self.user,
            encrypted_access_token="encrypted-token-placeholder",
        )

        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saby подключён.")
        self.assertContains(response, "Отключить Saby")
        self.assertNotContains(response, "Подключить Saby")
