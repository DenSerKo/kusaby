from asgiref.sync import sync_to_async
from django.shortcuts import render

from apps.accounts.decorators import api_login_required


@api_login_required
async def index(request):
    return sync_to_async(render)(request, 'core/index.html')