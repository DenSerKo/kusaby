from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


def api_login_required(view_func):
    """Require a Django user session and a connected Saby account."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            query = urlencode({"next": request.get_full_path()})
            login_url = f"{reverse('accounts:login')}?{query}"
            if request.headers.get("HX-Request") == "true":
                response = HttpResponse(status=204)
                response["HX-Redirect"] = login_url
                return response
            return redirect(login_url)

        if not request.session.get("saby_token"):
            messages.warning(request, "Сначала подключите Saby.")
            connect_url = reverse("core:index")
            if request.headers.get("HX-Request") == "true":
                response = HttpResponse(status=204)
                response["HX-Redirect"] = connect_url
                return response
            return redirect(connect_url)

        return view_func(request, *args, **kwargs)

    return wrapper
