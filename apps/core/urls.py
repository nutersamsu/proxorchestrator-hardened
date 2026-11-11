from django.urls import path

from . import console_auth
from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dashboard/node-summary/", views.dashboard_node_summary, name="dashboard_node_summary"),
    path("dashboard/job/<str:job_type>/<int:job_id>/", views.dashboard_job_status, name="dashboard_job_status"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("change-password/", views.change_password_view, name="change_password"),
    path("forgot-password/", views.password_reset_request, name="password_reset_request"),
    path("reset-password/<uidb64>/<token>/", views.password_reset_confirm, name="password_reset_confirm"),
    # MFA
    path("mfa/verify/", views.mfa_verify, name="mfa_verify"),
    path("mfa/setup/", views.mfa_setup, name="mfa_setup"),
    path("mfa/setup/confirm/", views.mfa_setup_confirm, name="mfa_setup_confirm"),
    path("mfa/disable/", views.mfa_disable, name="mfa_disable"),
    path("mfa/recovery/email/", views.mfa_email_recovery, name="mfa_email_recovery"),
    path("help/<slug:slug>/", views.help_view, name="help"),
    # nginx auth_request target for the /vm-ws/ console proxy
    path("internal/console-auth/", console_auth.console_ws_auth, name="console_ws_auth"),
]
