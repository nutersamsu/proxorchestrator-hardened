from django.urls import path

from . import views

urlpatterns = [
    path("", views.access_page, name="pveaccess_page"),
    path("<str:tab>/", views.access_page, name="pveaccess_tab"),
]
