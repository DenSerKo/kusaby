from typing import Any

from .client import DocumentsClient
from .filters import EventsFilter, filter_documents
from .parsers import parse_document_details


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

    documents = filter_documents(documents, filters)

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


async def approve_saby_document(
    token: str,
    prepare_params: dict[str, Any],
    execute_params: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Подготавливает и выполняет действие над документом в одной Saby-сессии."""
    async with DocumentsClient(token=token) as client:
        prepare_response = await client.prepare_action(prepare_params)
        execute_response = await client.execute_action(execute_params)

    def normalize_result(response: dict[str, Any]) -> list[dict[str, Any]]:
        result = response.get("result", [])
        if isinstance(result, dict):
            return [result]
        return result if isinstance(result, list) else []

    return {
        "prepare_result": normalize_result(prepare_response),
        "execute_result": normalize_result(execute_response),
    }


async def get_monitoring_events_page(
    token: str,
    *,
    from_datetime: str,
    last_event_id: str | None = None,
    last_event_datetime: str | None = None,
    last_event_document_id: str | None = None,
    last_organization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Получает одну страницу событий без пользовательских фильтров."""
    api_filter: dict[str, Any] = {
        "ДатаВремяС": last_event_datetime or from_datetime,
        "Навигация": {"РазмерСтраницы": 50},
        "ПолныйСертификатЭП": "Нет",
    }
    if last_event_id:
        api_filter["ИдентификаторСобытия"] = last_event_id
    if last_event_document_id:
        api_filter["ИдентификаторДокумента"] = last_event_document_id
    if last_organization:
        if last_organization.get("СвЮЛ"):
            legal = last_organization["СвЮЛ"]
            api_filter["НашаОрганизация"] = {
                "СвЮЛ": {
                    key: legal[key]
                    for key in ("ИНН", "КПП", "КодФилиала")
                    if legal.get(key)
                }
            }
        elif last_organization.get("СвФЛ"):
            individual = last_organization["СвФЛ"]
            api_filter["НашаОрганизация"] = {
                "СвФЛ": {
                    key: individual[key]
                    for key in ("ИНН", "КодФилиала")
                    if individual.get(key)
                }
            }

    async with DocumentsClient(token=token) as client:
        response = await client.get_events({"Фильтр": api_filter})

    result = response.get("result") or {}
    raw_documents = result.get("Документ") or []
    if isinstance(raw_documents, dict):
        raw_documents = [raw_documents]
    if not isinstance(raw_documents, list):
        raw_documents = []

    documents = [
        parse_document_details(document)
        for document in raw_documents
        if isinstance(document, dict)
    ]
    navigation = result.get("Навигация") or {}

    last_raw_document = next(
        (document for document in reversed(raw_documents) if isinstance(document, dict)),
        None,
    )
    raw_events = (last_raw_document or {}).get("Событие") or []
    if isinstance(raw_events, dict):
        raw_events = [raw_events]
    last_raw_event = raw_events[-1] if raw_events else {}
    raw_organization = (last_raw_document or {}).get("НашаОрганизация") or {}
    organization = {
        key: raw_organization[key]
        for key in ("СвЮЛ", "СвФЛ")
        if raw_organization.get(key)
    }

    return {
        "documents": documents,
        "has_more": navigation.get("ЕстьЕще") == "Да",
        "cursor": {
            "event_id": last_raw_event.get("Идентификатор"),
            "event_datetime": last_raw_event.get("ДатаВремя"),
            "document_id": (last_raw_document or {}).get("Идентификатор"),
            "organization": organization,
        },
    }
