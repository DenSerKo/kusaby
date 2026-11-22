from decimal import Decimal

from django.test import SimpleTestCase

from .filters import (
    EventsFilter,
    filter_documents,
    filter_documents_by_amount,
    filter_documents_by_counterparty,
    filter_documents_by_event_name,
    filter_unapproved_documents,
)


class DocumentFiltersTests(SimpleTestCase):
    def setUp(self):
        self.documents = [
            {
                "id": "org-match",
                "amount": "1500.00",
                "counterparty": {"inn": "1234567890", "kpp": "123456789"},
                "state": {"Название": "Ожидает утверждения"},
                "events": [{"name": "Изменение", "action_name": "Утверждение"}],
            },
            {
                "id": "ip-match",
                "amount": "2500.00",
                "counterparty": {"inn": "123456789012", "kpp": None},
                "state": {"Название": "Ожидает утверждения"},
                "events": [{"name": "Изменение", "action_name": "Утверждение"}],
            },
            {
                "id": "wrong-kpp",
                "amount": "1800.00",
                "counterparty": {"inn": "1234567890", "kpp": "987654321"},
                "state": {"Название": "Ожидает утверждения"},
                "events": [{"name": "Изменение", "action_name": "Утверждение"}],
            },
            {
                "id": "approved",
                "amount": "1700.00",
                "counterparty": {"inn": "1234567890", "kpp": "123456789"},
                "state": {"Название": "Выполнение завершено успешно"},
                "events": [{"name": "Изменение", "action_name": "Утверждение"}],
            },
            {
                "id": "other-action",
                "amount": "1600.00",
                "counterparty": {"inn": "1234567890", "kpp": "123456789"},
                "state": {"Название": "Ожидает утверждения"},
                "events": [{"name": "Другое событие", "action_name": "Согласование"}],
            },
        ]

    def test_amount_filter_uses_inclusive_boundaries(self):
        result = filter_documents_by_amount(
            self.documents,
            amount_min=Decimal("1500"),
            amount_max=Decimal("1800"),
        )
        self.assertEqual(
            [document["id"] for document in result],
            ["org-match", "wrong-kpp", "approved"],
        )

    def test_counterparty_filter_supports_inn_and_kpp(self):
        result = filter_documents_by_counterparty(
            self.documents,
            inn="1234567890",
            kpp="123456789",
        )
        self.assertEqual(
            [document["id"] for document in result],
            ["org-match", "approved"],
        )

    def test_counterparty_filter_supports_individual_inn_without_kpp(self):
        result = filter_documents_by_counterparty(
            self.documents,
            inn="123456789012",
        )
        self.assertEqual([document["id"] for document in result], ["ip-match"])

    def test_event_name_filter(self):
        result = filter_documents_by_event_name(self.documents, "Изменение")
        self.assertEqual(
            [document["id"] for document in result],
            ["org-match", "ip-match", "wrong-kpp", "approved"],
        )

    def test_unapproved_filter(self):
        result = filter_unapproved_documents(self.documents)
        self.assertEqual(
            [document["id"] for document in result],
            ["org-match", "ip-match", "wrong-kpp"],
        )

    def test_combined_filter_pipeline(self):
        filters = EventsFilter(
            from_datetime="01.11.2026 00.00.00",
            amount_min=Decimal("1400"),
            amount_max=Decimal("2000"),
            counterparty_inn="1234567890",
            counterparty_kpp="123456789",
        )
        result = filter_documents(self.documents, filters)
        self.assertEqual([document["id"] for document in result], ["org-match"])
