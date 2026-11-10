from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


def api_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("saby_token"):
            messages.warning(request, "Требуется авторизация")
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"{reverse('accounts:login')}?{query}")

        return view_func(request, *args, **kwargs)

    return wrapper
