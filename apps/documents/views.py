from datetime import datetime, timedelta
import logging

import httpx
from asgiref.sync import async_to_sync
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.decorators import api_login_required
from apps.documents.filters import EventsFilter
from apps.documents.services import get_organizations, get_events, prepare_action

logger = logging.getLogger(__name__)


@api_login_required
def index(request):
    return render(request, 'documents/index.html')

@api_login_required
def organizations(request):
    token = request.session["saby_token"]
    params = {
        "Фильтр": {}
    }

    try:
        organizations = async_to_sync(get_organizations)(token, params)
    except (httpx.HTTPError, ValueError):
        logger.exception("Не удалось получить список организаций СБИС")
        messages.error(request, "Не удалось получить список организаций")

        organizations = []

    return render(
        request,
        "documents/organizations.html",
        {"organizations": organizations},
    )

@api_login_required
def events(request):
    token = request.session["saby_token"]

    from_datetime = request.POST.get("from_datetime")

    if from_datetime:
        from_datetime = datetime.strptime(from_datetime, "%Y-%m-%dT%H:%M")
        from_datetime = timezone.make_aware(from_datetime)
    else:
        from_datetime = timezone.now() - timedelta(days=30)

    from_datetime = f"{timezone.localtime(from_datetime):%d.%m.%Y %H.%M.%S}"

    last_event_id = request.POST.get('last_event_id')
    if last_event_id:
        filters = EventsFilter(
            last_event_id=last_event_id
        )
    else:
        filters = EventsFilter(
            from_datetime=from_datetime,
        )

    try:
        events_data = async_to_sync(get_events)(token, filters)
    except (httpx.HTTPError, ValueError):
        logger.exception("Не удалось получить список изменений")
        messages.error(request, "Не удалось получить список изменений")
        events_data = {}

    context = {
        "events": events_data.get('events', []),
        "has_more": events_data.get('has_more', False),
        "last_event_id": events_data.get('last_event_id'),
    }
    if request.method == "POST":
        return render(request, "documents/partials/_events.html", context)
    return render(request,"documents/events.html", context)

def approve_document(request):
    token = request.session["saby_token"]
    document_id = request.POST.get("document_id")
    if document_id:
        params = {
            "Документ": {
                "Идентификатор": document_id,
                "Этап": {
                    "Действие": {
                        "Название": "Утвердить",
                        "Сертификат": {
                            "ИНН": "2537824180",
                            "ФИО": "Распутин Григорий Ефимович"
                        }
                    },
                    "Название": "Утверждение"
                }
            }
        }
        result = async_to_sync(prepare_action)(token, params)
        return HttpResponse(result)
    return HttpResponse('Документ не найден')