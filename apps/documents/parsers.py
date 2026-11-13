from datetime import datetime
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_party(party: dict[str, Any] | None) -> dict[str, Any]:
    """
    Приводит сведения о стороне документа к единой структуре.

    Для юридического лица СБИС передаёт реквизиты в СвЮЛ,
    для ИП — в СвФЛ. При этом Тип стороны обычно содержит
    значение "ЮЛ" или "ИП".
    """
    party = _as_dict(party)

    legal_entity = _as_dict(party.get("СвЮЛ"))
    individual = _as_dict(party.get("СвФЛ"))

    if legal_entity:
        name = legal_entity.get("Название")
        inn = legal_entity.get("ИНН")
        kpp = legal_entity.get("КПП")
        surname = first_name = patronymic = snils = country_code = None
    elif individual:
        surname = individual.get("Фамилия")
        first_name = individual.get("Имя")
        patronymic = individual.get("Отчество")
        name = (
            individual.get("НазваниеПолное")
            or " ".join(
                part for part in (surname, first_name, patronymic) if part
            )
            or None
        )
        inn = individual.get("ИНН")
        kpp = None
        snils = individual.get("СНИЛС")
        country_code = individual.get("КодСтраны")
    else:
        name = inn = kpp = None
        surname = first_name = patronymic = snils = country_code = None

    return {
        "name": name,
        "inn": inn,
        "kpp": kpp,
        "type": party.get("Тип"),
        "surname": surname,
        "first_name": first_name,
        "patronymic": patronymic,
        "snils": snils,
        "country_code": country_code,
        "email": party.get("Email"),
        "phone": party.get("Телефон"),
    }


def parse_document(document: dict[str, Any]) -> dict[str, Any]:
    counterparty = parse_party(document.get("Контрагент"))
    organization = parse_party(document.get("НашаОрганизация"))
    regulation = _as_dict(document.get("Регламент"))

    return {
        "id": document.get("Идентификатор"),
        "name": document.get("Название"),
        "number": document.get("Номер"),
        "date_created": parse_datetime(document.get("ДатаВремяСоздания")),
        "amount": document.get("Сумма"),
        "direction": document.get("Направление"),
        "counterparty": counterparty,
        "organization": organization,
        "regulation": regulation.get("Название"),
    }


def parse_attachment(attachment: dict[str, Any]) -> dict[str, Any]:
    signatures = attachment.get("Подпись") or []

    if isinstance(signatures, dict):
        signatures = [signatures]

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


def parse_signature(signature: dict[str, Any]) -> dict[str, Any]:
    certificate = _as_dict(signature.get("Сертификат"))

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
    action = _as_dict(event.get("Действие"))
    attachments = event.get("Вложение") or []

    if isinstance(attachments, dict):
        attachments = [attachments]

    return {
        "id": event.get("Идентификатор"),
        "name": event.get("Название"),
        "date": event.get("ДатаВремя"),
        "state": event.get("Состояние") or {},
        "action": action,
        "action_name": action.get("Название"),
        "attachments": [
            parse_attachment(attachment)
            for attachment in attachments
            if isinstance(attachment, dict)
        ],
    }


def parse_document_details(document: dict[str, Any]) -> dict[str, Any]:
    result = parse_document(document)
    events = document.get("Событие") or []

    if isinstance(events, dict):
        events = [events]

    result["events"] = [
        parse_event(event)
        for event in events
        if isinstance(event, dict)
    ]

    return result


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
            event.get("action_name") == event_action_name
            for event in document.get("events", [])
        )
    ]
