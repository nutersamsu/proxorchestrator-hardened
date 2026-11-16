from django.urls import path

from . import views

urlpatterns = [
    path("", views.node_page, name="node_page"),
    path("smart/", views.node_smart, name="node_smart"),
    path("<str:tab>/", views.node_page, name="node_tab"),
]
