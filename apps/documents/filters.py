from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass
class EventsFilter:
    """Параметры выборки событий и локальной фильтрации документов."""

    from_datetime: str
    to_datetime: str | None = None
    last_event_datetime: str | None = None
    last_event_id: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None


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
