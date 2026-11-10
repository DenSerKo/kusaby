from .client import DocumentsClient


async def get_organizations(token: str) -> None:
    async with DocumentsClient(token=token) as client:
        return await client.get_organizations()
