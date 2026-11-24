from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import models


class SabyConnection(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saby_connection",
    )
    encrypted_access_token = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_access_token(self, token: str) -> None:
        key = settings.SABY_TOKEN_ENCRYPTION_KEY
        if not key:
            raise ImproperlyConfigured(
                "SABY_TOKEN_ENCRYPTION_KEY must be configured to store Saby tokens."
            )
        self.encrypted_access_token = Fernet(key.encode()).encrypt(
            token.encode()
        ).decode()

    def get_access_token(self) -> str:
        key = settings.SABY_TOKEN_ENCRYPTION_KEY
        if not key:
            raise ImproperlyConfigured(
                "SABY_TOKEN_ENCRYPTION_KEY must be configured to read Saby tokens."
            )
        return Fernet(key.encode()).decrypt(
            self.encrypted_access_token.encode()
        ).decode()
