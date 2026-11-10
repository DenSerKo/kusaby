from .client import DocumentsClient


async def get_organizations(token: str, params: dict) -> None:
    async with DocumentsClient(token=token) as client:
        result = await client.get_organizations(params)
        return result['result']['НашаОрганизация']

async def get_events(token: str, params: dict) -> None:
    async with DocumentsClient(token=token) as client:
        result = await client.get_events(params)
        return result['result']['Документ']
