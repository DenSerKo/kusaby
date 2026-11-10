import httpx
from asgiref.sync import async_to_sync
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .services import login_to_saby, logout_from_saby


def login_view(request):
    if request.session.get("saby_token"):
        return redirect("core:index")

    next_url = request.POST.get("next") or request.GET.get("next") or "/"

    if request.method == "GET":
        return render(request, "accounts/login.html", {"next": next_url})

    if request.method != "POST":
        return redirect("accounts:login")

    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")

    if not username or not password:
        messages.error(request, "Введите логин и пароль")
        return render(request, "accounts/login.html", {"next": next_url})

    try:
        data = async_to_sync(login_to_saby)(username, password)
    except (httpx.HTTPError, ValueError):
        messages.error(request, "Не удалось выполнить запрос к СБИС. Попробуйте позже.")
        return render(request, "accounts/login.html", {"next": next_url})

    token = data.get("result") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token:
        messages.error(request, "СБИС не подтвердил авторизацию. Проверьте логин и пароль.")
        return render(request, "accounts/login.html", {"next": next_url})

    # Меняем ключ сессии после успешной авторизации.
    request.session.cycle_key()
    request.session["saby_token"] = token

    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)

    return redirect("core:index")


def logout_view(request):
    if request.method != "POST":
        return redirect("core:index")

    token = request.session.get("saby_token")

    if token:
        try:
            async_to_sync(logout_from_saby)(token)
        except (httpx.HTTPError, ValueError):
            # Локальную сессию завершаем, даже если API СБИС недоступно.
            pass

    request.session.flush()
    return redirect("accounts:login")
