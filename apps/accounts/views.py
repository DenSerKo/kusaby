import hmac
import logging
import secrets
from urllib.parse import urlencode

import httpx
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .oauth import exchange_code_for_token

logger = logging.getLogger(__name__)


@require_GET
def login_view(request):
    if request.session.get("saby_token"):
        return redirect("core:index")
    return render(request, "accounts/login.html")


@require_GET
def saby_authorize(request):

    # Исправить. Пока молча подает авторизация при неверном секрет.

    if request.session.get("saby_token"):
        return redirect("core:index")

    if not settings.SABY_CLIENT_ID or not settings.SABY_CLIENT_SECRET:
        messages.error(request, "Не настроены параметры OAuth приложения Saby.")
        return redirect("accounts:login")

    state = secrets.token_urlsafe(32)
    request.session["saby_oauth_state"] = state

    # This exact URL must be registered as the redirect URI in the Saby app settings.
    redirect_uri = settings.SABY_REDIRECT_URI
    params = {
        "client_id": settings.SABY_CLIENT_ID,
        "response_type": "code",
        "state": state,
        "redirect_uri": redirect_uri,
    }
    return redirect(f"{settings.SABY_OAUTH_AUTHORIZE_URL}?{urlencode(params)}")


def _callback_page(request, message: str):
    response = render(
        request,
        "accounts/saby_callback.html",
        {"message": message},
    )
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


@require_GET
def saby_callback(request):
    expected_state = request.session.pop("saby_oauth_state", None)
    received_state = request.GET.get("state", "")

    if (
        not expected_state
        or not received_state
        or not hmac.compare_digest(expected_state, received_state)
    ):
        messages.error(
            request,
            "Не удалось подтвердить авторизацию Saby (state не совпадает). "
            "Попробуйте подключиться ещё раз.",
        )
        return _callback_page(
            request,
            "Не удалось подтвердить авторизацию. Это окно можно закрыть.",
        )

    if request.GET.get("error"):
        messages.error(request, "Авторизация в Saby не была завершена.")
        return _callback_page(
            request,
            "Авторизация не завершена. Это окно можно закрыть.",
        )

    code = request.GET.get("code")
    if not code:
        messages.error(request, "Saby не вернул код авторизации.")
        return _callback_page(
            request,
            "Не получен код авторизации. Это окно можно закрыть.",
        )

    try:
        access_token = async_to_sync(exchange_code_for_token)(code)
    except (httpx.HTTPError, ValueError):
        logger.exception("Не удалось обменять Saby authorization code на access token")
        messages.error(
            request,
            "Не удалось получить токен доступа от Saby. Попробуйте позже.",
        )
        return _callback_page(
            request,
            "Не удалось завершить авторизацию. Это окно можно закрыть.",
        )

    request.session.cycle_key()
    request.session["saby_token"] = access_token
    messages.success(request, "Saby успешно подключён.")

    return _callback_page(
        request,
        "Авторизация завершена. Это окно закроется автоматически.",
    )


@require_POST
def logout_view(request):
    # The current OAuth prototype only stores the access token locally.
    # Do not call the legacy SBIS session logout method with an OAuth token.
    request.session.flush()
    messages.success(request, "Вы отключили Saby.")
    return redirect("core:index")
