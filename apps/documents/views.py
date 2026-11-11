import datetime
import logging

import httpx
from asgiref.sync import async_to_sync
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render

from apps.accounts.decorators import api_login_required
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
    from_datetime = datetime.datetime.now() - datetime.timedelta(days=365)
    from_datetime = f"{from_datetime:%d.%m.%Y %H.%M.%S}"
    params = {
        "Фильтр": {
            "ДатаВремяС": from_datetime,
            "Тип": "ДокОтгрВх",
        }
    }

    try:
        events = async_to_sync(get_events)(token, params)
    except (httpx.HTTPError, ValueError):
        logger.exception("Не удалось получить список изменений")
        messages.error(request, "Не удалось получить список изменений")
        events = []

    return render(
        request,
        "documents/events.html",
        {'events': events},
    )

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