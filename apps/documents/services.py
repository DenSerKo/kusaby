from typing import Any

from .client import DocumentsClient
from .filters import EventsFilter
from .parsers import (
    filter_documents_by_event_action_name,
    parse_document_details,
)


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
        response = await client.get_organizations(params)

    result = response.get("result", {})
    organizations = result.get("НашаОрганизация", [])

    if isinstance(organizations, dict):
        organizations = [organizations]

    if not isinstance(organizations, list):
        return []

    return organizations


async def get_events(
    token: str,
    filters: EventsFilter,
) -> dict[str, Any]:
    params = _build_events_params(filters)

    async with DocumentsClient(token=token) as client:
        response = await client.get_events(params)

    result = response.get("result", {})
    if not isinstance(result, dict):
        result = {}

    raw_documents = result.get("Документ", [])
    if isinstance(raw_documents, dict):
        raw_documents = [raw_documents]
    elif not isinstance(raw_documents, list):
        raw_documents = []

    navigation = result.get("Навигация") or {}
    has_more = navigation.get("ЕстьЕще", "Нет") == "Да"

    documents = [
        parse_document_details(document)
        for document in raw_documents
        if isinstance(document, dict)
    ]

    last_event_id = None
    if documents:
        last_events = documents[-1].get("events", [])
        if last_events:
            last_event_id = last_events[-1].get("id")

    documents = filter_documents_by_event_action_name(
        documents,
        "Утверждение",
    )

    return {
        "events": documents,
        "has_more": has_more,
        "last_event_id": last_event_id,
    }


async def prepare_action(
    token: str,
    params: dict,
) -> list[dict[str, Any]]:
    async with DocumentsClient(token=token) as client:
        response = await client.prepare_action(params)

    result = response.get("result", [])
    if isinstance(result, dict):
        result = [result]

    if not isinstance(result, list):
        return []

    return result
