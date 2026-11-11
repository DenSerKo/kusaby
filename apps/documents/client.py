from django.conf import settings

from clients.base import BaseClient


class DocumentsClient(BaseClient):
    async def get_organizations(self, params: dict) -> dict:
        return await self.jsonrpc(
            settings.SABY_API_SERVICE_ENDPOINT,
            "СБИС.СписокНашихОрганизаций",
            params
        )

    async def get_events(self, params: dict) -> dict:
        return await self.jsonrpc(
            settings.SABY_API_SERVICE_ENDPOINT,
            "СБИС.СписокИзменений",
            params
        )

    async def prepare_action(self, params: dict) -> dict:
        return await self.jsonrpc(
            settings.SABY_API_SERVICE_ENDPOINT,
            "СБИС.ПодготовитьДействие",
            params
        )
