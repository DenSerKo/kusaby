from typing import Any


def parse_document(document: dict[str, Any]) -> dict[str, Any]:
    counterparty = document.get("Контрагент") or {}
    counterparty_info = counterparty.get("СвЮЛ") or {}

    organization = document.get("НашаОрганизация") or {}
    organization_info = organization.get("СвЮЛ") or {}

    regulation = document.get("Регламент") or {}

    return {
        "id": document.get("Идентификатор"),
        "name": document.get("Название"),
        "number": document.get("Номер"),
        "date_created": parse_datetime(document.get("ДатаВремяСоздания")),
        "amount": document.get("Сумма"),

        "direction": document.get("Направление"),

        "counterparty": {
            "name": counterparty_info.get("Название"),
            "inn": counterparty_info.get("ИНН"),
            "kpp": counterparty_info.get("КПП"),
        },

        "organization": {
            "name": organization_info.get("Название"),
            "inn": organization_info.get("ИНН"),
            "kpp": organization_info.get("КПП"),
        },

        "regulation": regulation.get("Название"),
    }

def parse_attachment(
    attachment: dict[str, Any],
) -> dict[str, Any]:

    signatures = attachment.get("Подпись") or []

    return {
        "id": attachment.get("Идентификатор"),
        "name": attachment.get("Название"),
        "number": attachment.get("Номер"),
        "date": attachment.get("Дата"),
        "type": attachment.get("Тип"),
        "file": attachment.get("Файл") or {},
        "signatures": [
            parse_signature(signature)
            for signature in signatures
            if isinstance(signature, dict)
        ],
    }


def parse_signature(
    signature: dict[str, Any],
) -> dict[str, Any]:

    certificate = signature.get("Сертификат") or {}

    return {
        "direction": signature.get("Направление"),
        "type": signature.get("Тип"),
        "certificate": {
            "name": certificate.get("Название"),
            "inn": certificate.get("ИНН"),
            "fio": certificate.get("ФИО"),
            "valid_from": certificate.get("ДействителенС"),
            "valid_to": certificate.get("ДействителенПо"),
            "fingerprint": certificate.get("Отпечаток"),
        },
    }

def parse_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event.get("Идентификатор"),
        "name": event.get("Название"),
        "date": event.get("ДатаВремя"),
        "state": event.get("Состояние") or {},
        "action": event.get("Действие") or {},
        "attachments": [
            parse_attachment(attachment)
            for attachment in event.get("Вложение", [])
            if isinstance(attachment, dict)
        ],
    }

def parse_document_details(
    document: dict[str, Any],
) -> dict[str, Any]:

    result = parse_document(document)

    result["events"] = [
        parse_event(event)
        for event in document.get("Событие", [])
        if isinstance(event, dict)
    ]

    return result

from datetime import datetime


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    return datetime.strptime(value, "%d.%m.%Y %H.%M.%S")


def filter_documents_by_event_name(
    documents: list[dict[str, Any]],
    event_name: str,
) -> list[dict[str, Any]]:

    return [
        document
        for document in documents
        if any(
            event.get("name") == event_name
            for event in document.get("events", [])
        )
    ]

def filter_documents_by_event_action_name(
    documents: list[dict[str, Any]],
    event_action_name: str,
) -> list[dict[str, Any]]:

    return [
        document
        for document in documents
        if any(
            event.get("action", []).get("Название") == event_action_name
            for event in document.get("events", [])
        )
    ]