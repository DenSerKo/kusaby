from dataclasses import dataclass


@dataclass
class EventsFilter:
    """Пользовательский период и отдельный курсор постраничной загрузки."""

    from_datetime: str
    to_datetime: str | None = None
    last_event_datetime: str | None = None
    last_event_id: str | None = None
