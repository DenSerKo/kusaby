from functools import wraps
from urllib.parse import urlencode

from asgiref.sync import sync_to_async
from django.contrib import messages
from django.shortcuts import redirect


def api_login_required(view_func):
    @wraps(view_func)
    async def wrapper(request, *args, **kwargs):
        if not request.session.get("api_token"):
            await sync_to_async(messages.warning)(request, "Требуется авторизация")
            next_url = request.get_full_path()
            login_url = f"/accounts/login/?{urlencode({'next': next_url})}"
            return redirect(login_url)
        return await view_func(request, *args, **kwargs)

    return wrapper