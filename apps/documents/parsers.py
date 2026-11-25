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
        "private_person": individual.get("ЧастноеЛицо"),
        "external_id": party.get("ИдентификаторИС"),
        "description": party.get("Описание"),
        "email": party.get("Email"),
        "phone": party.get("Телефон"),
    }



def _get_saby_url(document: dict[str, Any]) -> str | None:
    direct_url = (
        document.get("СсылкаДляНашаОрганизация")
        or document.get("СсылкаДляКонтрагент")
    )
    if direct_url:
        return direct_url

    events = document.get("Событие") or []
    if isinstance(events, dict):
        events = [events]
    for event in events:
        if not isinstance(event, dict):
            continue
        attachments = event.get("Вложение") or []
        if isinstance(attachments, dict):
            attachments = [attachments]
        for attachment in attachments:
            if isinstance(attachment, dict) and attachment.get("СсылкаВКабинет"):
                return attachment["СсылкаВКабинет"]
    return None


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
        "state": document.get("Состояние"),
        "saby_url": _get_saby_url(document),
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

    parsed_events = [
        parse_event(event)
        for event in events
        if isinstance(event, dict)
    ]
    result["events"] = parsed_events

    # Вложения приходят внутри событий документа. Собираем их в общий
    # список, сохраняя порядок и исключая повторения по идентификатору.
    attachments = []
    seen_attachments = set()

    for event in parsed_events:
        for attachment in event["attachments"]:
            attachment_id = attachment.get("id")
            attachment_name = attachment.get("name")
            key = ("id", attachment_id) if attachment_id else ("name", attachment_name)

            if not attachment_name or key in seen_attachments:
                continue

            seen_attachments.add(key)
            attachments.append(attachment)

    result["attachments"] = attachments

    return result


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    return datetime.strptime(value, "%d.%m.%Y %H.%M.%S")
