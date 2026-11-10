import httpx
from asgiref.sync import async_to_sync
from django.shortcuts import render, redirect

from apps.accounts.decorators import api_login_required
from apps.documents.services import get_organizations


@api_login_required
def index(request):
    return render(request, 'documents/index.html')

@api_login_required
def organizations(request):

    token = request.session.get("saby_token")

    organizations = []
    if token:
        try:
            organizations = async_to_sync(get_organizations)(token)['result']['НашаОрганизация']
        except (httpx.HTTPError, ValueError):
            pass
    return render(request,
                  'documents/organizations.html',
                  {'organizations': organizations})


# git test