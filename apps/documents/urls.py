from django.urls import path

from apps.documents import views


app_name = 'documents'
urlpatterns = [
    path('', views.index, name='index'),
    path('organizations/', views.organizations, name='organizations'),
    path('events/', views.events, name='events'),
    path('approve-document/', views.approve_document, name='approve-document'),
]