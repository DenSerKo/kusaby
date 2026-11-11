from django.conf import settings

from clients.base import BaseClient


class AuthClient(BaseClient):

    async def login(self, username: str, password: str) -> dict:
        return await self.jsonrpc(
            settings.SABY_API_AUTH_ENDPOINT,
            "СБИС.Аутентифицировать",
            {
                "Параметр": {
                    "Логин": username,
                    "Пароль": password,
                }
            },
        )

    async def logout(self) -> dict:
        if not self.token:
            return {}

        return await self.jsonrpc(
            settings.SABY_API_AUTH_ENDPOINT,
            "СБИС.Выход",
            {},
        )