from clients.base import BaseClient


class DocumentsClient(BaseClient):
    async def get_organizations(self) -> dict:
        return await self.post(
            "/service/?srv=1",
            json={
               "jsonrpc": "2.0",
               "method": "СБИС.СписокНашихОрганизаций",
               "params": {
                  "Фильтр": {}
               },
               "id": 0
            },
        )
