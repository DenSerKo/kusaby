from django.contrib.auth.views import LoginView
from django.urls import path

from .views import (
    disconnect_saby,
    logout_view,
    saby_authorize,
    saby_callback,
)

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(
            template_name="accounts/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("saby/authorize/", saby_authorize, name="saby_authorize"),
    path("saby/callback/", saby_callback, name="saby_callback"),
    path("saby/disconnect/", disconnect_saby, name="saby_disconnect"),
    path("logout/", logout_view, name="logout"),
]
