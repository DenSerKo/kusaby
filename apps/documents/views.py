import logging
from datetime import datetime, timedelta

import httpx
from asgiref.sync import async_to_sync
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import api_login_required
from apps.documents.filters import EventsFilter
from apps.documents.services import get_events, get_organizations, prepare_action
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
def events(request):
    # Фильтр передаётся через query string для GET и через POST
    # при htmx-пагинации/совместимых POST-запросах.
    params = request.GET if request.method == "GET" else request.POST
    value = params.get("from_datetime")

    try:
        if value:
            start = timezone.make_aware(
                datetime.strptime(value, "%Y-%m-%dT%H:%M")
            )
        else:
            start = timezone.now() - timedelta(days=30)
    except ValueError:
        context = {
            "events": [],
            "has_more": False,
            "last_event_id": None,
            "from_datetime": value or "",
            "error_message": "Некорректно указана дата начала периода.",
        }
        template = (
            "documents/partials/_events.html"
            if request.method == "POST"
            else "documents/events.html"
        )
        return render(request, template, context, status=400)

    # Передаём значение обратно в input, чтобы состояние формы
    # соответствовало фильтру, использованному в запросе.
    from_datetime = timezone.localtime(start).strftime("%Y-%m-%dT%H:%M")

    event_id = request.POST.get("last_event_id")
    filters = (
        EventsFilter(last_event_id=event_id)
        if event_id
        else EventsFilter(
            from_datetime=timezone.localtime(start).strftime(
                "%d.%m.%Y %H.%M.%S"
            )
        )
    )

    try:
        data = async_to_sync(get_events)(
            request.session["saby_token"], filters
        )
        status = 200
    except (SabyAPIError, SabyResponseError, httpx.HTTPError) as exc:
        _log_error(exc, "get_events")
        message, details, status = _error_context(exc)
        data = {
            "events": [],
            "has_more": False,
            "last_event_id": None,
            "error_message": message,
            "error_details": details,
        }

    context = {
        "events": data.get("events", []),
        "has_more": data.get("has_more", False),
        "last_event_id": data.get("last_event_id"),
        "error_message": data.get("error_message"),
        "error_details": data.get("error_details"),
        "from_datetime": from_datetime,
    }
    template = (
        "documents/partials/_events.html"
        if request.method == "POST"
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

    params = {"Документ": {
        "Идентификатор": document_id,
        "Этап": {
            "Действие": {"Название": "Утвердить", "Сертификат": {
                "ИНН": "2537824180", "ФИО": "Распутин Григорий Ефимович",
            }},
            "Название": "Утверждение",
        },
    }}

    try:
        async_to_sync(prepare_action)(request.session["saby_token"], params)
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
