from django.urls import path

from . import views

urlpatterns = [
    path("", views.backups_index, name="backups_index"),
    path("new/", views.backup_new, name="backup_new"),
    path("restore/", views.backup_restore, name="backup_restore"),
    path("protect/", views.backup_protect, name="backup_protect"),
    path("notes/", views.backup_notes, name="backup_notes"),
    path("delete/", views.volume_delete, name="volume_delete"),
    path("job/<str:job_id>/run/", views.backup_job_run, name="backup_job_run"),
    path("guest/<str:kind>/<int:vmid>/", views.guest_backups, name="guest_backups"),
    path("guest/<str:kind>/<int:vmid>/now/", views.guest_backup_now, name="guest_backup_now"),
]
