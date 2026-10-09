"""Accounts API views: register, login, logout, current user."""

from __future__ import annotations

import logging

from django.contrib.auth import authenticate, get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nazbeen_forex_ai.accounts.models import UserProfile
from nazbeen_forex_ai.accounts.serializers import RegisterSerializer, UserSerializer
from nazbeen_forex_ai.core.throttling import ResilientScopedRateThrottle

logger = logging.getLogger(__name__)
User = get_user_model()


class RegisterView(APIView):
    """POST /api/auth/register/ — create an account and return a token."""

    permission_classes = [AllowAny]
    throttle_scope = "auth"
    throttle_classes = [ResilientScopedRateThrottle]

    def post(self, request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        UserProfile.objects.get_or_create(user=user)
        token, _ = Token.objects.get_or_create(user=user)
        logger.info("Registered new user id=%s", user.pk)
        return Response(
            {"token": token.key, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """POST /api/auth/login/ — credential check returning an API token."""

    permission_classes = [AllowAny]
    throttle_scope = "auth"
    throttle_classes = [ResilientScopedRateThrottle]

    def post(self, request) -> Response:
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is None:
            # Uniform message: never reveal whether the account exists.
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    """POST /api/auth/logout/ — delete the caller's token."""

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        if request.user.is_authenticated:
            Token.objects.filter(user=request.user).delete()
        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


class MeView(APIView):
    """GET /api/auth/me/ — the authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        UserProfile.objects.get_or_create(user=request.user)
        return Response(UserSerializer(request.user).data)
