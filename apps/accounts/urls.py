from django.urls import path

from .views import login_view, logout_view, saby_authorize, saby_callback

app_name = "accounts"

urlpatterns = [
    path("login/", login_view, name="login"),
    path("saby/authorize/", saby_authorize, name="saby_authorize"),
    path("saby/callback/", saby_callback, name="saby_callback"),
    path("logout/", logout_view, name="logout"),
]
