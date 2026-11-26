from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from apps.accounts.models import SabyConnection

from .automation import _parse_amount
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


class SabyDocumentLinkTests(SimpleTestCase):
    def test_parse_document_keeps_direct_saby_link(self):
        from .parsers import parse_document

        document = {
            "Идентификатор": "document-1",
            "СсылкаДляНашаОрганизация": "https://online.saby.ru/doc/1",
        }
        self.assertEqual(
            parse_document(document)["saby_url"],
            "https://online.saby.ru/doc/1",
        )

    def test_parse_document_falls_back_to_cabinet_link_in_event_attachment(self):
        from .parsers import parse_document

        document = {
            "Идентификатор": "document-2",
            "Событие": [{
                "Вложение": [{
                    "СсылкаВКабинет": "https://online.saby.ru/doc/2",
                }],
            }],
        }
        self.assertEqual(
            parse_document(document)["saby_url"],
            "https://online.saby.ru/doc/2",
        )


from .models import ApprovalItem, ApprovalRule, ApprovalRun
from .tasks import _refresh_run_status


class ApprovalAutomationModelTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="automation-test",
            password="test-password",
        )
        self.connection = SabyConnection.objects.create(
            user=user,
            encrypted_access_token="encrypted-test-token",
        )
        self.rule = ApprovalRule.objects.create(
            connection=self.connection,
            name="Test rule",
        )
        self.run = ApprovalRun.objects.create(
            user=user,
            connection=self.connection,
            rule=self.rule,
            trigger=ApprovalRun.Trigger.AUTOMATIC,
            criteria={},
        )

    def test_rule_is_disabled_by_default(self):
        self.assertFalse(self.rule.is_active)
        self.assertEqual(
            self.rule.interval_minutes,
            ApprovalRule.Interval.FIVE_MINUTES,
        )

    def test_database_prevents_duplicate_document_for_same_rule(self):
        ApprovalItem.objects.create(
            run=self.run,
            rule=self.rule,
            connection=self.connection,
            document_id="document-1",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ApprovalItem.objects.create(
                run=self.run,
                rule=self.rule,
                connection=self.connection,
                document_id="document-1",
            )

    def test_different_rules_can_track_the_same_document(self):
        other_rule = ApprovalRule.objects.create(
            connection=self.connection,
            name="Another rule",
        )
        other_run = ApprovalRun.objects.create(
            user=self.run.user,
            connection=self.connection,
            rule=other_rule,
            trigger=ApprovalRun.Trigger.AUTOMATIC,
        )
        ApprovalItem.objects.create(
            run=self.run,
            rule=self.rule,
            connection=self.connection,
            document_id="document-1",
            status=ApprovalItem.Status.SUCCEEDED,
        )
        other_item = ApprovalItem.objects.create(
            run=other_run,
            rule=other_rule,
            connection=self.connection,
            document_id="document-1",
        )
        self.assertEqual(other_item.document_id, "document-1")

    def test_run_status_waits_for_all_items(self):
        pending = ApprovalItem.objects.create(
            run=self.run,
            connection=self.connection,
            document_id="document-pending",
            status=ApprovalItem.Status.PENDING,
        )
        ApprovalItem.objects.create(
            run=self.run,
            connection=self.connection,
            document_id="document-queued",
            status=ApprovalItem.Status.QUEUED,
        )

        _refresh_run_status(self.run.pk)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, ApprovalRun.Status.RUNNING)

        ApprovalItem.objects.filter(pk=pending.pk).update(
            status=ApprovalItem.Status.SUCCEEDED,
        )
        ApprovalItem.objects.filter(
            run=self.run,
            document_id="document-queued",
        ).update(status=ApprovalItem.Status.PENDING)

        _refresh_run_status(self.run.pk)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, ApprovalRun.Status.PENDING)

        ApprovalItem.objects.filter(
            run=self.run,
            document_id="document-queued",
        ).update(status=ApprovalItem.Status.SUCCEEDED)

        _refresh_run_status(self.run.pk)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, ApprovalRun.Status.COMPLETED)



class ApprovalRuleCriteriaTests(SimpleTestCase):
    def test_amount_parser_accepts_decimal_comma(self):
        from decimal import Decimal

        self.assertEqual(_parse_amount("1250,50"), Decimal("1250.50"))

    def test_amount_parser_rejects_negative_amount(self):
        with self.assertRaises(ValueError):
            _parse_amount("-1")
