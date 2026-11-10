from django.shortcuts import render

from apps.accounts.decorators import api_login_required


@api_login_required
def index(request):
    return render(request, "core/index.html")
