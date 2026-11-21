import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx
from asgiref.sync import async_to_sync
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.decorators import api_login_required
from apps.documents.filters import EventsFilter
from apps.documents.services import get_events, get_organizations, prepare_action, execute_action
from clients.exceptions import SabyAPIError, SabyResponseError

logger = logging.getLogger(__name__)


def _error_context(exc):
    if isinstance(exc, SabyAPIError):
        return exc.message, exc.details, exc.http_status or 502
    if isinstance(exc, httpx.HTTPStatusError):
        body = exc.response.text.strip()
        message = f"СБИС вернул HTTP {exc.response.status_code}."
        return f"{message} {body[:2000]}" if body else message, None, exc.response.status_code
    return "Не удалось связаться с СБИС или обработать его ответ. Попробуйте позже.", None, 502


def _log_error(exc, operation):
    if isinstance(exc, SabyAPIError):
        logger.error(
            "Ошибка СБИС: operation=%s method=%s status=%s code=%s type=%s message=%s details=%s",
            operation, exc.method, exc.http_status, exc.code,
            exc.error_type, exc.message, exc.details,
        )
    elif isinstance(exc, httpx.HTTPStatusError):
        logger.error("HTTP-ошибка СБИС: operation=%s status=%s body=%s",
                     operation, exc.response.status_code, exc.response.text[:2000])
    else:
        logger.exception("Ошибка взаимодействия с СБИС: operation=%s", operation)


def _parse_filter_datetime(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M")
    return timezone.make_aware(parsed, timezone.get_current_timezone())


def _parse_filter_amount(value: str) -> Decimal | None:
    if not value:
        return None

    try:
        amount = Decimal(value.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Укажите корректную сумму в фильтре по сумме.") from exc

    if not amount.is_finite() or amount < 0:
        raise ValueError("Сумма должна быть неотрицательным числом.")

    return amount


def _parse_filter_inn(value: str) -> str | None:
    if not value:
        return None
    if not value.isascii() or not value.isdigit() or len(value) not in (10, 12):
        raise ValueError("ИНН должен содержать 10 цифр для организации или 12 цифр для ИП.")
    return value


def _parse_filter_kpp(value: str) -> str | None:
    if not value:
        return None
    if not value.isascii() or not value.isdigit() or len(value) != 9:
        raise ValueError("КПП должен содержать 9 цифр.")
    return value


def _get_counterparty_filter(
    inn_value: str,
    kpp_value: str,
) -> tuple[str | None, str | None]:
    inn = _parse_filter_inn(inn_value)
    kpp = _parse_filter_kpp(kpp_value)

    if kpp and not inn:
        raise ValueError("Для фильтра по КПП необходимо указать ИНН организации.")
    if kpp and len(inn) != 10:
        raise ValueError("КПП можно указать только вместе с 10-значным ИНН организации.")

    return inn, kpp


def _format_saby_datetime(value: datetime) -> str:
    return timezone.localtime(value).strftime("%d.%m.%Y %H.%M.%S")


@api_login_required
def index(request):
    return render(request, "documents/index.html")


@api_login_required
def organizations(request):
    context = {"organizations": []}
    status = 200
    try:
        context["organizations"] = async_to_sync(get_organizations)(
            request.session["saby_token"], {"Фильтр": {}}
        )
    except (SabyAPIError, SabyResponseError, httpx.HTTPError) as exc:
        _log_error(exc, "get_organizations")
        context["error_message"], context["error_details"], status = _error_context(exc)
    return render(request, "documents/organizations.html", context, status=status)


@api_login_required
@require_GET
def events(request):
    from_value = request.GET.get("from_datetime", "").strip()
    to_value = request.GET.get("to_datetime", "").strip()
    amount_min_value = request.GET.get("amount_min", "").strip()
    amount_max_value = request.GET.get("amount_max", "").strip()
    counterparty_inn_value = request.GET.get("counterparty_inn", "").strip()
    counterparty_kpp_value = request.GET.get("counterparty_kpp", "").strip()
    event_id = request.GET.get("last_event_id", "").strip() or None
    event_datetime = request.GET.get("last_event_datetime", "").strip() or None

    try:
        # Для нового поиска начало по умолчанию — месяц назад.
        # При пагинации сохраняем именно исходное начало фильтра.
        if from_value:
            start = _parse_filter_datetime(from_value)
        else:
            start = timezone.now() - timedelta(days=30)

        end = _parse_filter_datetime(to_value) if to_value else None
        amount_min = _parse_filter_amount(amount_min_value)
        amount_max = _parse_filter_amount(amount_max_value)
        counterparty_inn, counterparty_kpp = _get_counterparty_filter(
            counterparty_inn_value,
            counterparty_kpp_value,
        )

        if end and end < start:
            raise ValueError("Конец периода раньше его начала.")
        if amount_min is not None and amount_max is not None and amount_min > amount_max:
            raise ValueError("Минимальная сумма не может быть больше максимальной.")

    except ValueError as exc:
        context = {
            "events": [],
            "has_more": False,
            "last_event_id": None,
            "last_event_datetime": None,
            "from_datetime": from_value,
            "to_datetime": to_value,
            "amount_min": amount_min_value,
            "amount_max": amount_max_value,
            "counterparty_inn": counterparty_inn_value,
            "counterparty_kpp": counterparty_kpp_value,
            "error_message": str(exc) or "Проверьте параметры фильтра.",
        }
        template = (
            "documents/partials/_events.html"
            if request.headers.get("HX-Request-Type") == "partial"
            else "documents/events.html"
        )
        return render(request, template, context, status=400)

    from_datetime = timezone.localtime(start).strftime("%Y-%m-%dT%H:%M")
    to_datetime = timezone.localtime(end).strftime("%Y-%m-%dT%H:%M") if end else ""

    filters = EventsFilter(
        from_datetime=_format_saby_datetime(start),
        to_datetime=_format_saby_datetime(end) if end else None,
        last_event_datetime=event_datetime,
        last_event_id=event_id,
        amount_min=amount_min,
        amount_max=amount_max,
        counterparty_inn=counterparty_inn,
        counterparty_kpp=counterparty_kpp,
    )

    try:
        data = async_to_sync(get_events)(request.session["saby_token"], filters)
        status = 200
    except (SabyAPIError, SabyResponseError, httpx.HTTPError) as exc:
        _log_error(exc, "get_events")
        message, details, status = _error_context(exc)
        data = {
            "events": [],
            "has_more": False,
            "last_event_id": None,
            "last_event_datetime": None,
            "error_message": message,
            "error_details": details,
        }

    context = {
        "events": data.get("events", []),
        "has_more": data.get("has_more", False),
        "last_event_id": data.get("last_event_id"),
        "last_event_datetime": data.get("last_event_datetime"),
        "error_message": data.get("error_message"),
        "error_details": data.get("error_details"),
        "from_datetime": from_datetime,
        "to_datetime": to_datetime,
        "amount_min": amount_min_value,
        "amount_max": amount_max_value,
        "counterparty_inn": counterparty_inn_value,
        "counterparty_kpp": counterparty_kpp_value,
        "is_pagination": bool(event_id),
    }
    template = (
        "documents/partials/_events.html"
        if request.headers.get("HX-Request-Type") == "partial"
        else "documents/events.html"
    )
    return render(request, template, context, status=status)


@api_login_required
@require_POST
def approve_document(request):
    document_id = request.POST.get("document_id")
    if not document_id:
        return render(request, "documents/partials/_approve_result.html", {
            "document_id": "", "success": False,
            "message": "Не указан идентификатор документа.", "details": None,
        }, status=400)

    params = {
        "Документ": {
            "Идентификатор": document_id,
            "Этап": {
                "Действие":{
                    "Название": "Утвердить",
                    "Сертификат": {
                        "ИНН": "2537824180", "ФИО": "Романов Николай Александрович",
                    }
                },
                "Название": "Утверждение",
            },
        }
    }

    try:
        async_to_sync(prepare_action)(request.session["saby_token"], params)
    except (SabyAPIError, SabyResponseError, httpx.HTTPError) as exc:
        _log_error(exc, "approve_document")
        message, details, status = _error_context(exc)
        return render(request, "documents/partials/_approve_result.html", {
            "document_id": document_id, "success": False,
            "message": message, "details": details,
        }, status=status)

    params = {
            "Документ": {
                "Идентификатор": document_id,
                "Этап": {
                    "Действие": {
                        "Название": "Утвердить",
                        "Сертификат": {}
                    },
                    "Название": "Утверждение"
                }
            }
        }

    try:
        async_to_sync(execute_action)(request.session["saby_token"], params)
    except (SabyAPIError, SabyResponseError, httpx.HTTPError) as exc:
        _log_error(exc, "approve_document")
        message, details, status = _error_context(exc)
        return render(request, "documents/partials/_approve_result.html", {
            "document_id": document_id, "success": False,
            "message": message, "details": details,
        }, status=status)

    return render(request, "documents/partials/_approve_result.html", {
        "document_id": document_id, "success": True,
        "message": "СБИС успешно обработал запрос на утверждение.", "details": None,
    })
