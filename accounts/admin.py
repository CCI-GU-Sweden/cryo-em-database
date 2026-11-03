from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class RegistryUserAdmin(UserAdmin):
    def has_delete_permission(self, request, obj=None):
        # Deactivate accounts instead: later grid events must retain their actor.
        return False

    fieldsets = UserAdmin.fieldsets + (("Registry access", {"fields": ("is_cci_staff",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Registry access", {"fields": ("is_cci_staff",)}),)
    list_display = (*UserAdmin.list_display, "is_cci_staff")
