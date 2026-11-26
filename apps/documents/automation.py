import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from asgiref.sync import async_to_sync
from django.db import IntegrityError, transaction
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task

from apps.documents.filters import EventsFilter
from apps.documents.models import ApprovalItem, ApprovalRule, ApprovalRun
from apps.documents.services import get_events
from apps.documents.tasks import approve_document_task, _refresh_run_status

logger = logging.getLogger(__name__)


@db_periodic_task(crontab(minute="*"))
def dispatch_approval_rules() -> None:
    """Ставит в очередь запуски правил, срок которых наступил."""
    now = timezone.now()
    due_rule_ids = list(
        ApprovalRule.objects
        .filter(is_active=True, next_run_at__lte=now)
        .values_list("pk", flat=True)
    )

    for rule_id in due_rule_ids:
        run_id = None
        try:
            with transaction.atomic():
                rule = (
                    ApprovalRule.objects
                    .select_related("connection", "connection__user")
                    .filter(pk=rule_id, is_active=True, next_run_at__lte=now)
                    .first()
                )
                if rule is None:
                    continue

                next_run_at = now + timedelta(minutes=rule.interval_minutes)
                claimed = ApprovalRule.objects.filter(
                    pk=rule.pk,
                    is_active=True,
                    next_run_at=rule.next_run_at,
                ).update(
                    next_run_at=next_run_at,
                    last_run_at=now,
                    last_error="",
                )
                if not claimed:
                    continue

                run = ApprovalRun.objects.create(
                    user=rule.connection.user,
                    connection=rule.connection,
                    rule=rule,
                    trigger=ApprovalRun.Trigger.AUTOMATIC,
                    criteria=rule.criteria,
                )
                run_id = run.pk

            # Enqueue only after the rule claim and run have committed.
            process_approval_rule_task(run_id)
        except Exception as exc:
            logger.exception("Could not dispatch approval rule=%s", rule_id)
            if run_id is not None:
                ApprovalRun.objects.filter(pk=run_id).update(
                    status=ApprovalRun.Status.FAILED,
                    finished_at=timezone.now(),
                )
            ApprovalRule.objects.filter(pk=rule_id).update(last_error=str(exc)[:4000])


@db_task()
def process_approval_rule_task(run_id: int) -> None:
    """Ищет документы по снимку критериев правила и ставит их на утверждение."""
    run = (
        ApprovalRun.objects
        .select_related("rule", "connection")
        .get(pk=run_id)
    )
    rule = run.rule
    if rule is None or run.connection is None:
        _fail_rule_run(run, "Правило или подключение Saby больше недоступно.")
        return

    try:
        criteria = run.criteria or {}
        scan_from = rule.last_checked_at or (
            rule.created_at - timedelta(minutes=5)
        )
        amount_min = _parse_amount(criteria.get("amount_min"))
        amount_max = _parse_amount(criteria.get("amount_max"))
        if amount_min is not None and amount_max is not None and amount_min > amount_max:
            raise ValueError("Минимальная сумма в правиле больше максимальной.")

        inn = str(criteria.get("counterparty_inn") or "").strip()
        kpp = str(criteria.get("counterparty_kpp") or "").strip()
        if inn and (not inn.isascii() or not inn.isdigit() or len(inn) not in (10, 12)):
            raise ValueError("ИНН в правиле должен содержать 10 или 12 цифр.")
        if kpp and (not kpp.isascii() or not kpp.isdigit() or len(kpp) != 9):
            raise ValueError("КПП в правиле должен содержать 9 цифр.")
        if kpp and len(inn) != 10:
            raise ValueError("КПП можно указать только вместе с 10-значным ИНН организации.")

        filters = EventsFilter(
            from_datetime=timezone.localtime(scan_from).strftime("%d.%m.%Y %H.%M.%S"),
            amount_min=amount_min,
            amount_max=amount_max,
            counterparty_inn=inn or None,
            counterparty_kpp=kpp or None,
        )

        token = run.connection.get_access_token()
        documents = []
        seen_cursors = set()
        for _ in range(100):
            page = async_to_sync(get_events)(token, filters)
            documents.extend(page["events"])
            if not page["has_more"]:
                break

            cursor = (page["last_event_datetime"], page["last_event_id"])
            if not all(cursor) or cursor in seen_cursors:
                raise RuntimeError("Saby вернул некорректный курсор пагинации.")
            seen_cursors.add(cursor)
            filters.last_event_datetime, filters.last_event_id = cursor
        else:
            raise RuntimeError("Превышен лимит страниц при поиске документов по правилу.")

        # Do not automatically process the same document twice under one rule.
        processed_ids = set(
            ApprovalItem.objects
            .filter(rule=rule)
            .values_list("document_id", flat=True)
        )
        candidates = [
            document for document in documents
            if document.get("id") and document["id"] not in processed_ids
        ]

        new_items = []
        for document in candidates:
            try:
                with transaction.atomic():
                    item = ApprovalItem.objects.create(
                        run=run,
                        rule=rule,
                        connection=run.connection,
                        document_id=document["id"],
                        saby_url=document.get("saby_url") or "",
                    )
                new_items.append(item)
            except IntegrityError:
                # Another manual/automatic run may already be processing it.
                continue

        now = timezone.now()
        ApprovalRule.objects.filter(pk=rule.pk).update(
            last_checked_at=now,
            last_error="",
        )

        if not new_items:
            run.status = ApprovalRun.Status.COMPLETED
            run.started_at = run.started_at or now
            run.finished_at = now
            run.save(update_fields=["status", "started_at", "finished_at"])
            return

        run.status = ApprovalRun.Status.QUEUED
        run.started_at = run.started_at or now
        run.finished_at = None
        run.save(update_fields=["status", "started_at", "finished_at"])

        for item in new_items:
            try:
                approve_document_task(item.pk)
            except Exception as exc:
                logger.exception(
                    "Could not enqueue automatic approval item=%s",
                    item.pk,
                )
                item.status = ApprovalItem.Status.FAILED
                item.message = "Не удалось поставить документ в очередь на утверждение."
                item.details = str(exc)[:4000]
                item.save(update_fields=["status", "message", "details", "updated_at"])

        _refresh_run_status(run.pk)

    except Exception as exc:
        logger.exception("Automatic approval run failed: run=%s", run_id)
        _fail_rule_run(run, str(exc))


def _parse_amount(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("В правиле указана некорректная сумма.") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Сумма в правиле должна быть неотрицательной.")
    return amount


def _fail_rule_run(run: ApprovalRun, message: str) -> None:
    now = timezone.now()
    run.status = ApprovalRun.Status.FAILED
    run.finished_at = now
    run.save(update_fields=["status", "finished_at"])
    if run.rule_id:
        ApprovalRule.objects.filter(pk=run.rule_id).update(last_error=message[:4000])
