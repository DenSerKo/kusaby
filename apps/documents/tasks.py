import logging

import httpx
from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from huey.contrib.djhuey import db_task

from apps.documents.models import ApprovalItem, ApprovalRun
from apps.documents.services import approve_saby_document
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
    except (httpx.TimeoutException, httpx.TransportError, SabyResponseError) as exc:
        logger.exception("Неизвестен результат утверждения документа %s", item.document_id)
        _finish_item(
            item_id,
            ApprovalItem.Status.UNKNOWN,
            "Не удалось достоверно определить результат. Проверьте документ в Saby перед повторным запуском.",
            str(exc),
        )
    except (SabyAPIError, httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.exception("Не удалось утвердить документ %s", item.document_id)
        _finish_item(
            item_id,
            ApprovalItem.Status.FAILED,
            "Saby не подтвердил выполнение утверждения.",
            str(exc),
        )
    except Exception as exc:
        logger.exception("Не удалось определить результат утверждения %s", item.document_id)
        _finish_item(
            item_id,
            ApprovalItem.Status.UNKNOWN,
            "Результат операции неизвестен. Проверьте документ в Saby перед повторным запуском.",
            str(exc),
        )
    else:
        _finish_item(
            item_id,
            ApprovalItem.Status.SUCCEEDED,
            "Saby обработал запрос на утверждение.",
            "",
        )


def _finish_item(item_id: int, status: str, message: str, details: str) -> None:
    now = timezone.now()
    with transaction.atomic():
        item = ApprovalItem.objects.select_related("run").get(pk=item_id)
        item.status = status
        item.message = message
        item.details = details[:4000]
        item.save(update_fields=["status", "message", "details", "updated_at"])

        item.run.status = (
            ApprovalRun.Status.COMPLETED
            if status == ApprovalItem.Status.SUCCEEDED
            else ApprovalRun.Status.FAILED
        )
        item.run.finished_at = now
        item.run.save(update_fields=["status", "finished_at"])
