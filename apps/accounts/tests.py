from cryptography.fernet import Fernet
from django.test import SimpleTestCase, override_settings

from .models import SabyConnection


class SabyConnectionTests(SimpleTestCase):
    @override_settings(SABY_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode())
    def test_access_token_is_encrypted_and_can_be_decrypted(self):
        connection = SabyConnection()
        connection.set_access_token("sample-access-token")

        self.assertNotEqual(
            connection.encrypted_access_token,
            "sample-access-token",
        )
        self.assertEqual(
            connection.get_access_token(),
            "sample-access-token",
        )
