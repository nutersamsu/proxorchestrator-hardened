from django.urls import path

from . import views

urlpatterns = [
    path("", views.storage_list, name="datastore_list"),
    path("<str:storage>/", views.storage_content, name="datastore_content"),
]
