from typing import Any

from .client import DocumentsClient
from .filters import (
    EventsFilter,
    filter_documents_by_amount,
    filter_documents_by_counterparty,
)
from .parsers import parse_document_details, filter_unapproved_documents


def _build_events_params(filters: EventsFilter) -> dict[str, Any]:
    api_filter: dict[str, Any] = {
        "Тип": "ДокОтгрВх",
        "Навигация": {
            "РазмерСтраницы": 50,
        },
        "ДатаВремяС": (
            filters.last_event_datetime
            if filters.last_event_id and filters.last_event_datetime
            else filters.from_datetime
        ),
    }

    if filters.to_datetime:
        api_filter["ДатаВремяПо"] = filters.to_datetime

    if filters.last_event_id and filters.last_event_datetime:
        api_filter["ИдентификаторСобытия"] = filters.last_event_id

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

    # Курсор берём из последнего события исходного ответа, до локальной
    # фильтрации документов: иначе отфильтрованные записи могут зациклить страницы.
    last_event = None
    for document in reversed(documents):
        if document.get("events"):
            last_event = document["events"][-1]
            break

    documents = filter_unapproved_documents(documents)
    documents = filter_documents_by_amount(
        documents,
        amount_min=filters.amount_min,
        amount_max=filters.amount_max,
    )
    documents = filter_documents_by_counterparty(
        documents,
        inn=filters.counterparty_inn,
        kpp=filters.counterparty_kpp,
    )

    return {
        "events": documents,
        "has_more": has_more,
        "last_event_id": last_event.get("id") if last_event else None,
        "last_event_datetime": last_event.get("date") if last_event else None,
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


async def execute_action(
    token: str,
    params: dict,
) -> list[dict[str, Any]]:
    async with DocumentsClient(token=token) as client:
        response = await client.execute_action(params)

    result = response.get("result", [])
    if isinstance(result, dict):
        result = [result]

    if not isinstance(result, list):
        return []

    return result
