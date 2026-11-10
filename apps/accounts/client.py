from django.conf import settings

from clients.base import BaseClient


class AuthClient(BaseClient):
    async def login(self, username: str, password: str) -> dict:
        return await self.post(
            settings.SABY_API_AUTH_ENDPOINT,
            json={
                'jsonrpc': '2.0',
                'method': 'СБИС.Аутентифицировать',
                'params': {
                    'Параметр': {
                        'Логин': username,
                        'Пароль': password
                    }
                },
                'id': 0
            },
        )

    async def logout(self) -> None:
        if not self.token:
            return
        await self.post(
            settings.SABY_API_AUTH_ENDPOINT,
            json={
                'jsonrpc': '2.0',
                'method': 'СБИС.Выход',
                'params': {},
                'id': 0
            },
        )