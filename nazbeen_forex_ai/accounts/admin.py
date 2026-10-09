"""Accounts admin registration."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from nazbeen_forex_ai.accounts.models import UserProfile

User = get_user_model()


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_timezone", "created_at")
    search_fields = ("user__username",)


# Re-register the default User with the standard admin if not already present.
if not admin.site.is_registered(User):
    admin.site.register(User, DjangoUserAdmin)
