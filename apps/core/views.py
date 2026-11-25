from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.models import SabyConnection


@login_required
def index(request):
    context = {
        "saby_connected": SabyConnection.objects.filter(user=request.user).exists(),
    }
    return render(request, "core/index.html", context)
