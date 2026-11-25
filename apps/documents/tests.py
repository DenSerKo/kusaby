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
            ["org-match", "wrong-kpp", "approved", "other-action"],
        )

    def test_counterparty_filter_supports_inn_and_kpp(self):
        result = filter_documents_by_counterparty(
            self.documents,
            inn="1234567890",
            kpp="123456789",
        )
        self.assertEqual(
            [document["id"] for document in result],
            ["org-match", "approved", "other-action"],
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


class ApproveSabyDocumentTests(SimpleTestCase):
    async def test_approval_uses_one_client_for_prepare_and_execute(self):
        from unittest.mock import AsyncMock, patch

        from .services import approve_saby_document

        client = AsyncMock()
        client.__aenter__.return_value = client
        client.prepare_action.return_value = {"result": {"status": "prepared"}}
        client.execute_action.return_value = {"result": {"status": "executed"}}

        prepare_params = {"document": "prepare"}
        execute_params = {"document": "execute"}

        with patch("apps.documents.services.DocumentsClient", return_value=client) as factory:
            result = await approve_saby_document(
                "test-token",
                prepare_params,
                execute_params,
            )

        factory.assert_called_once_with(token="test-token")
        client.prepare_action.assert_awaited_once_with(prepare_params)
        client.execute_action.assert_awaited_once_with(execute_params)
        client.__aexit__.assert_awaited_once()
        self.assertEqual(result["prepare_result"], [{"status": "prepared"}])
        self.assertEqual(result["execute_result"], [{"status": "executed"}])
