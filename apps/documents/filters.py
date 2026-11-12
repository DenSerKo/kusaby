from dataclasses import dataclass


@dataclass
class EventsFilter:
    from_datetime: str | None = None
    last_event_id: str | None = None