from urllib.parse import urlparse

from asgiref.sync import sync_to_async
from django.shortcuts import render, redirect
from django.views import View

from .client import AuthClient


def is_safe_url(url: str, host: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return not parsed.netloc or parsed.netloc == host


class LoginView(View):
    template_name = "accounts/login.html"

    async def get(self, request):
        token = await sync_to_async(request.session.get)("X-SBISSessionID")
        if token:
            return redirect("/")

        next_url = request.GET.get("next", "/")
        return await sync_to_async(render)(request, self.template_name, {"next": next_url})

    async def post(self, request):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        next_url = request.POST.get("next") or "/"

        if not username or not password:
            return await sync_to_async(render)(request, self.template_name, {"next": next_url})

        try:
            async with AuthClient() as client:
                data = await client.login(username, password)
        except Exception:
            return await sync_to_async(render)(request, self.template_name, {"next": next_url})

        token = data.get("result") if data else None
        if not token:
            return await sync_to_async(render)(request, self.template_name, {"next": next_url})

        # Сохраняем в сессию
        await sync_to_async(request.session.__setitem__)("X-SBISSessionID", token)
        await sync_to_async(request.session.save)()

        if is_safe_url(next_url, request.get_host()):
            return redirect(next_url)
        return redirect("/")


class LogoutView(View):
    async def post(self, request):
        token = await sync_to_async(request.session.get)("X-SBISSessionID")

        if token:
            try:
                async with AuthClient(token=token) as client:
                    await client.logout()
            except Exception:
                pass

        await sync_to_async(request.session.flush)()
        return redirect("accounts:login")

    async def get(self, request):
        return await self.post(request)