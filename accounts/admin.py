from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class RegistryUserAdmin(UserAdmin):
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "is_staff":
            # Keep Django's permission flag; only clarify its label for operators.
            kwargs["label"] = "Administration site access"
            kwargs["help_text"] = (
                "Allows access to the administration site, subject to assigned permissions. "
                "Ordinary operators only need CCI staff member."
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(boolean=True, description="Administration site access", ordering="is_staff")
    def administration_site_access(self, user):
        return user.is_staff

    def has_delete_permission(self, request, obj=None):
        # Deactivate accounts instead: later grid events must retain their actor.
        return False

    fieldsets = UserAdmin.fieldsets + (("Registry access", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Registry access", {"fields": ("role",)}),)
    list_display = (
        *(
            "administration_site_access" if field == "is_staff" else field
            for field in UserAdmin.list_display
        ),
        "role",
    )
