from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass
class EventsFilter:
    """Параметры запроса событий и локальной фильтрации документов."""

    from_datetime: str
    to_datetime: str | None = None
    last_event_datetime: str | None = None
    last_event_id: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    counterparty_inn: str | None = None
    counterparty_kpp: str | None = None


def filter_documents_by_event_name(
    documents: list[dict[str, Any]],
    event_name: str,
) -> list[dict[str, Any]]:
    """Оставляет документы, содержащие событие с указанным названием."""
    return [
        document
        for document in documents
        if any(
            event.get("name") == event_name
            for event in document.get("events", [])
        )
    ]


def filter_unapproved_documents(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Оставляет документы, ожидающие утверждения."""
    return [
        document
        for document in documents
        if any(
            event.get("action_name") == "Утверждение"
            for event in document.get("events", [])
        )
        and (document.get("state") or {}).get("Название")
        != "Выполнение завершено успешно"
    ]


def filter_documents_by_amount(
    documents: list[dict[str, Any]],
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
) -> list[dict[str, Any]]:
    """Оставляет документы в заданном диапазоне суммы (границы включительно)."""
    if amount_min is None and amount_max is None:
        return documents

    filtered_documents = []

    for document in documents:
        raw_amount = document.get("amount")
        if raw_amount is None:
            continue

        try:
            amount = Decimal(str(raw_amount).strip().replace(",", "."))
        except (InvalidOperation, ValueError):
            continue

        if not amount.is_finite():
            continue
        if amount_min is not None and amount < amount_min:
            continue
        if amount_max is not None and amount > amount_max:
            continue

        filtered_documents.append(document)

    return filtered_documents


def filter_documents_by_counterparty(
    documents: list[dict[str, Any]],
    inn: str | None = None,
    kpp: str | None = None,
) -> list[dict[str, Any]]:
    """Оставляет документы с совпадающими ИНН и, при наличии, КПП контрагента."""
    if inn is None and kpp is None:
        return documents

    filtered_documents = []

    for document in documents:
        counterparty = document.get("counterparty") or {}
        document_inn = str(counterparty.get("inn") or "").strip()
        document_kpp = str(counterparty.get("kpp") or "").strip()

        if inn is not None and document_inn != inn:
            continue
        if kpp is not None and document_kpp != kpp:
            continue

        filtered_documents.append(document)

    return filtered_documents


def filter_documents(
    documents: list[dict[str, Any]],
    filters: EventsFilter,
) -> list[dict[str, Any]]:
    """Последовательно применяет локальные критерии к разобранным документам."""
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
    return documents
