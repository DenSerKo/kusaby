from typing import Any

from .client import DocumentsClient
from .filters import EventsFilter
from .parsers import parse_document, parse_document_details, filter_documents_by_event_name, \
    filter_documents_by_event_action_name


def _build_events_params(filters: EventsFilter) -> dict:
    api_filter = {
        "Тип": "ДокОтгрВх",
        "Навигация": {
            "РазмерСтраницы": 50,
        },
    }

    if filters.last_event_id:
        api_filter["ИдентификаторСобытия"] = filters.last_event_id
    elif filters.from_datetime:
        api_filter["ДатаВремяС"] = filters.from_datetime

    return {"Фильтр": api_filter}


async def get_organizations(
    token: str,
    params: dict,
) -> list[dict[str, Any]]:
    async with DocumentsClient(token=token) as client:
        result = await client.get_organizations(params)
        return result['result']['НашаОрганизация']

async def get_events(
        token: str,
        filters: EventsFilter) -> dict[str, Any]:
    params = _build_events_params(filters)
    async with DocumentsClient(token=token) as client:
        response = await client.get_events(params)

    result = response.get("result", {})
    raw_documents = result.get("Документ", [])

    has_more = result.get('Навигация', {}).get('ЕстьЕще', 'Нет') == 'Да'

    if isinstance(raw_documents, dict):
        raw_documents = [raw_documents]

    documents = [
        parse_document_details(document)
        for document in raw_documents
        if isinstance(document, dict)
    ]

    last_event_id = None
    last_event = documents[-1].get('events', [])
    if last_event:
        last_event_id = last_event[-1].get('id')

    documents =  filter_documents_by_event_action_name(
        documents,
        "Утверждение"
    )

    return {
        'events': documents,
        'has_more': has_more,
        'last_event_id': last_event_id,
    }

async def prepare_action(
    token: str,
    params: dict,
) -> list[dict[str, Any]]:
    async with DocumentsClient(token=token) as client:
        result = await client.prepare_action(params)
        return result['result']
