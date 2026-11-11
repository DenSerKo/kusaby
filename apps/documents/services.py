from typing import Any

from .client import DocumentsClient
from .parsers import parse_document, parse_document_details


async def get_organizations(
    token: str,
    params: dict,
) -> list[dict[str, Any]]:
    async with DocumentsClient(token=token) as client:
        result = await client.get_organizations(params)
        return result['result']['НашаОрганизация']

async def get_events(token: str, params: dict) -> list[dict]:
    async with DocumentsClient(token=token) as client:
        response = await client.get_events(params)

    documents = response.get("result", {}).get("Документ", [])

    if isinstance(documents, dict):
        documents = [documents]

    return [
        parse_document_details(document)
        for document in documents
        if isinstance(document, dict)
    ]

async def prepare_action(
    token: str,
    params: dict,
) -> list[dict[str, Any]]:
    async with DocumentsClient(token=token) as client:
        result = await client.prepare_action(params)
        return result['result']
