from django.urls import path

from . import views

urlpatterns = [
    path("", views.task_list, name="task_list"),
    path("recent/", views.tasks_recent, name="tasks_recent"),
    path("<str:upid>/", views.task_detail, name="task_detail"),
    path("<str:upid>/log/", views.task_log, name="task_log"),
    path("<str:upid>/stop/", views.task_stop, name="task_stop"),
]
