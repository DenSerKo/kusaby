import logging
from datetime import timedelta

import httpx
from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task

from apps.accounts.models import SabyConnection
from apps.documents.models import ApprovalItem, ApprovalRun, SabyEventsCursor
from apps.documents.services import approve_saby_document, get_monitoring_events_page
from clients.exceptions import SabyAPIError, SabyResponseError

logger = logging.getLogger(__name__)


@db_task()
def approve_document_task(item_id: int) -> None:
    """Выполняет утверждение одного документа и сохраняет итог."""
    with transaction.atomic():
        item = (
            ApprovalItem.objects
            .select_related("run", "connection")
            .get(pk=item_id)
        )
        if item.status != ApprovalItem.Status.QUEUED:
            return

        item.status = ApprovalItem.Status.RUNNING
        item.save(update_fields=["status", "updated_at"])
        item.run.status = ApprovalRun.Status.RUNNING
        item.run.started_at = timezone.now()
        item.run.save(update_fields=["status", "started_at"])

    try:
        certificate_inn = settings.SABY_APPROVAL_CERTIFICATE_INN
        certificate_name = settings.SABY_APPROVAL_CERTIFICATE_NAME
        if not certificate_inn or not certificate_name:
            raise RuntimeError(
                "Не настроены SABY_APPROVAL_CERTIFICATE_INN и "
                "SABY_APPROVAL_CERTIFICATE_NAME."
            )

        if item.connection is None:
            raise RuntimeError("Подключение Saby было отключено до выполнения задачи.")
        token = item.connection.get_access_token()
        prepare_params = {
            "Документ": {
                "Идентификатор": item.document_id,
                "Этап": {
                    "Действие": {
                        "Название": "Утвердить",
                        "Сертификат": {
                            "ИНН": certificate_inn,
                            "ФИО": certificate_name,
                        },
                    },
                    "Название": "Утверждение",
                },
            },
        }
        execute_params = {
            "Документ": {
                "Идентификатор": item.document_id,
                "Этап": {
                    "Действие": {
                        "Название": "Утвердить",
                        "Сертификат": {},
                    },
                    "Название": "Утверждение",
                },
            },
        }

        async_to_sync(approve_saby_document)(
            token,
            prepare_params,
            execute_params,
        )

    except SabyAPIError as exc:
        # JSON-RPC error is an explicit rejection returned by Saby.
        error_details = []
        if exc.method:
            error_details.append(f"Метод: {exc.method}")
        if exc.code is not None:
            error_details.append(f"Код: {exc.code}")
        if exc.details:
            error_details.append(str(exc.details))

        logger.warning(
            "Saby rejected approval: document=%s method=%s code=%s message=%s details=%s",
            item.document_id,
            exc.method,
            exc.code,
            exc.message,
            exc.details,
        )
        _finish_item(
            item_id,
            ApprovalItem.Status.FAILED,
            f"СБИС отклонил операцию: {exc.message}",
            "\\n".join(error_details),
        )

    except httpx.HTTPStatusError as exc:
        body = exc.response.text.strip()
        details = body[:4000] if body else str(exc)
        is_server_error = exc.response.status_code >= 500
        logger.warning(
            "Saby returned HTTP error: document=%s status=%s body=%s",
            item.document_id,
            exc.response.status_code,
            details,
        )
        _finish_item(
            item_id,
            ApprovalItem.Status.UNKNOWN if is_server_error else ApprovalItem.Status.FAILED,
            (
                "СБИС вернул ошибку сервера. Проверьте документ в Saby перед повторным запуском."
                if is_server_error
                else f"СБИС отклонил запрос (HTTP {exc.response.status_code})."
            ),
            details,
        )

    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.warning(
            "Saby connection failed during approval: document=%s error=%s",
            item.document_id,
            exc,
        )
        _finish_item(
            item_id,
            ApprovalItem.Status.UNKNOWN,
            "Не удалось достоверно определить результат из-за сетевой ошибки. "
            "Проверьте документ в Saby перед повторным запуском.",
            str(exc),
        )

    except SabyResponseError as exc:
        logger.warning(
            "Invalid Saby response during approval: document=%s error=%s",
            item.document_id,
            exc,
        )
        _finish_item(
            item_id,
            ApprovalItem.Status.UNKNOWN,
            "СБИС вернул ответ, который приложение не смогло корректно обработать. "
            "Проверьте документ в Saby перед повторным запуском.",
            str(exc),
        )

    except (RuntimeError, ValueError) as exc:
        logger.error(
            "Approval configuration or validation error: document=%s error=%s",
            item.document_id,
            exc,
        )
        _finish_item(
            item_id,
            ApprovalItem.Status.FAILED,
            "Не удалось подготовить утверждение. Проверьте настройки приложения.",
            str(exc),
        )

    except httpx.HTTPError as exc:
        logger.warning(
            "HTTP client error during approval: document=%s error=%s",
            item.document_id,
            exc,
        )
        _finish_item(
            item_id,
            ApprovalItem.Status.UNKNOWN,
            "Не удалось достоверно определить результат запроса. "
            "Проверьте документ в Saby перед повторным запуском.",
            str(exc),
        )

    except Exception as exc:
        # Unexpected programming/runtime errors still need a traceback for developers.
        logger.exception(
            "Unexpected error during approval: document=%s",
            item.document_id,
        )
        _finish_item(
            item_id,
            ApprovalItem.Status.UNKNOWN,
            "Произошла внутренняя ошибка. Результат операции требует проверки в Saby.",
            str(exc),
        )

    else:
        # ExecuteAction accepted the command; delayed signing is monitored separately.
        item = ApprovalItem.objects.get(pk=item_id)
        item.status = ApprovalItem.Status.PENDING
        item.accepted_at = timezone.now()
        item.message = "Saby принял запрос. Ожидаем подтверждения подписания."
        item.details = ""
        item.save(update_fields=["status", "accepted_at", "message", "details", "updated_at"])
        item.run.status = ApprovalRun.Status.PENDING
        item.run.save(update_fields=["status"])


def _finish_item(item_id: int, status: str, message: str, details: str) -> None:
    now = timezone.now()
    with transaction.atomic():
        item = ApprovalItem.objects.select_related("run").get(pk=item_id)
        item.status = status
        item.message = message
        item.details = details[:4000]
        item.save(update_fields=["status", "message", "details", "saby_url", "updated_at"])

        if status == ApprovalItem.Status.PENDING:
            item.run.status = ApprovalRun.Status.PENDING
            item.run.finished_at = None
            item.run.save(update_fields=["status", "finished_at"])
        else:
            item.run.status = (
                ApprovalRun.Status.COMPLETED
                if status == ApprovalItem.Status.SUCCEEDED
                else ApprovalRun.Status.FAILED
            )
            item.run.finished_at = now
            item.run.save(update_fields=["status", "finished_at"])


@db_periodic_task(crontab(minute="*/5"))
def sync_approval_events() -> None:
    """Сверяет ожидающие операции с общим потоком событий Saby."""
    overdue_after = timedelta(minutes=30)
    for connection in SabyConnection.objects.iterator():
        try:
            _sync_connection_events(connection, overdue_after)
        except Exception:
            logger.exception(
                "Failed to synchronize Saby events for connection=%s",
                connection.pk,
            )


def _sync_connection_events(connection, overdue_after) -> None:
    pending_items = ApprovalItem.objects.filter(
        connection=connection,
        status__in=(ApprovalItem.Status.PENDING, ApprovalItem.Status.OVERDUE),
    )
    if not pending_items.exists():
        return

    cursor, _ = SabyEventsCursor.objects.get_or_create(connection=connection)
    if cursor.last_event_datetime:
        start_datetime = cursor.last_event_datetime
    else:
        earliest = pending_items.order_by("accepted_at").first()
        start_datetime = timezone.localtime(
            earliest.accepted_at or earliest.created_at
        ).strftime("%d.%m.%Y %H.%M.%S")

    token = connection.get_access_token()
    # Ограничиваем число страниц за один запуск, чтобы периодическая задача
    # не занимала worker бесконечно при большом потоке событий.
    for _ in range(20):
        page = async_to_sync(get_monitoring_events_page)(
            token,
            from_datetime=start_datetime,
            last_event_id=cursor.last_event_id or None,
            last_event_datetime=cursor.last_event_datetime or None,
            last_event_document_id=cursor.last_event_document_id or None,
            last_organization=cursor.last_organization or None,
        )
        documents = page["documents"]
        for document in documents:
            item = ApprovalItem.objects.filter(
                connection=connection,
                document_id=document.get("id"),
                status__in=(ApprovalItem.Status.PENDING, ApprovalItem.Status.OVERDUE),
            ).first()
            if item is None:
                continue
            update_fields = []
            if document.get("saby_url") and item.saby_url != document["saby_url"]:
                item.saby_url = document["saby_url"]
                update_fields.append("saby_url")
            if (document.get("state") or {}).get("Название") != "Выполнение завершено успешно":
                if update_fields:
                    item.save(update_fields=update_fields + ["updated_at"])
                continue
            item.status = ApprovalItem.Status.SUCCEEDED
            item.message = "Документ успешно подписан в Saby."
            item.details = ""
            item.save(update_fields=["status", "message", "details", "updated_at"])
            item.run.status = ApprovalRun.Status.COMPLETED
            item.run.finished_at = timezone.now()
            item.run.save(update_fields=["status", "finished_at"])

        next_cursor = page["cursor"]
        if next_cursor["event_id"] and next_cursor["event_datetime"] and next_cursor["document_id"]:
            cursor.last_event_id = next_cursor["event_id"]
            cursor.last_event_datetime = next_cursor["event_datetime"]
            cursor.last_event_document_id = next_cursor["document_id"]
            cursor.last_organization = next_cursor["organization"] or {}
            cursor.save(update_fields=[
                "last_event_id",
                "last_event_datetime",
                "last_event_document_id",
                "last_organization",
                "updated_at",
            ])
        if not page["has_more"] or not documents:
            break

    cutoff = timezone.now() - overdue_after
    stale_items = ApprovalItem.objects.filter(
        connection=connection,
        status=ApprovalItem.Status.PENDING,
        accepted_at__lte=cutoff,
    )
    for item in stale_items.select_related("run"):
        item.status = ApprovalItem.Status.OVERDUE
        item.message = "Saby пока не подтвердил подписание. Проверьте документ в Saby."
        item.save(update_fields=["status", "message", "updated_at"])
        item.run.status = ApprovalRun.Status.PENDING
        item.run.save(update_fields=["status"])
