"""Accounts URL routes (mounted under ``/api/auth/``)."""

from django.urls import path

from nazbeen_forex_ai.accounts.views import LoginView, LogoutView, MeView, RegisterView

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
