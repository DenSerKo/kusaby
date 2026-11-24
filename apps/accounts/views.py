import hmac
import logging
import secrets
from urllib.parse import urlencode

import httpx
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from apps.accounts.models import SabyConnection
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .oauth import exchange_code_for_token, logout_from_saby

logger = logging.getLogger(__name__)


@require_GET
@login_required
def saby_authorize(request):
    if request.session.get("saby_token"):
        return redirect("core:index")

    if not settings.SABY_CLIENT_ID or not settings.SABY_CLIENT_SECRET:
        messages.error(request, "Не настроены параметры OAuth приложения Saby.")
        return redirect("core:index")

    state = secrets.token_urlsafe(32)
    request.session["saby_oauth_state"] = state

    params = {
        "client_id": settings.SABY_CLIENT_ID,
        "response_type": "code",
        "state": state,
        "redirect_uri": settings.SABY_REDIRECT_URI,
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
@login_required
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

    if not settings.SABY_TOKEN_ENCRYPTION_KEY:
        messages.error(
            request,
            "Не настроен ключ шифрования токена Saby. "
            "Добавьте SABY_TOKEN_ENCRYPTION_KEY в .env.",
        )
        return _callback_page(
            request,
            "Подключение не сохранено: не настроено шифрование токена.",
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

    connection, _ = SabyConnection.objects.get_or_create(user=request.user)
    connection.set_access_token(access_token)
    connection.save(update_fields=["encrypted_access_token", "updated_at"])

    request.session.cycle_key()
    request.session["saby_token"] = access_token
    messages.success(request, "Saby успешно подключён.")

    return _callback_page(
        request,
        "Авторизация завершена. Это окно закроется автоматически.",
    )


@require_POST
@login_required
def disconnect_saby(request):
    token = request.session.get("saby_token")

    if token:
        try:
            async_to_sync(logout_from_saby)(token)
        except httpx.HTTPError:
            logger.exception("Не удалось завершить Saby-сессию")
            messages.error(
                request,
                "Не удалось завершить сессию Saby. "
                "Токен оставлен в приложении; попробуйте отключить ещё раз.",
            )
            return redirect("core:index")

    SabyConnection.objects.filter(user=request.user).delete()
    request.session.pop("saby_token", None)
    request.session.pop("saby_oauth_state", None)
    messages.success(request, "Сессия Saby завершена, подключение отключено.")
    return redirect("core:index")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")
