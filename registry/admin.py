from django.contrib import admin
from django.http import HttpResponseNotAllowed, JsonResponse
from django.urls import path, reverse

from .forms import AdminOwnerForm, OwnerNameForm
from .models import AuditEvent, DeletedGrid, Grid, OwnerAccessGrant, PreparationSession, SampleOwner
from .services import save_administration_record, suggest_owner_code


class FacilityAdministration(admin.ModelAdmin):
    # Django's staff flag alone does not give facility-wide authority.
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        save_administration_record(
            actor=request.user,
            instance=obj,
            preferred_code=form.cleaned_data.get("owner_code_preview", ""),
        )


@admin.register(SampleOwner)
class SampleOwnerAdmin(FacilityAdministration):
    form = AdminOwnerForm
    list_display = ["name", "code", "affiliation", "active"]
    search_fields = ["name", "code"]
    fields = [
        "name",
        "owner_code_preview",
        "affiliation",
        "notes",
        "active",
        "created_at",
        "updated_at",
    ]
    readonly_fields = ["created_at", "updated_at"]

    class Media:
        js = ["owner_code.js"]
        css = {"all": ["owner_admin.css"]}

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["name"].widget.attrs["data-code-url"] = reverse(
            "admin:registry_sampleowner_suggest_code"
        )
        return form

    def get_urls(self):
        return [
            path(
                "suggest-code/",
                self.admin_site.admin_view(self.suggest_code),
                name="registry_sampleowner_suggest_code",
            ),
            *super().get_urls(),
        ]

    def suggest_code(self, request):
        if not self.has_add_permission(request):
            return JsonResponse({"error": "Only an administrator can register owners."}, status=403)
        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])
        form = OwnerNameForm(request.GET)
        if not form.is_valid():
            return JsonResponse(
                {"error": "Enter an owner name of up to 200 characters."}, status=400
            )
        return JsonResponse({"code": suggest_owner_code(form.cleaned_data["name"])})


@admin.register(OwnerAccessGrant)
class OwnerAccessGrantAdmin(FacilityAdministration):
    list_display = ["user", "owner", "role"]
    readonly_fields = ["created_at", "updated_at"]


class ReadOnlyRecordAdmin(FacilityAdministration):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# All scientific mutations go through the staff UI/services, even for administrators.
@admin.register(Grid)
class ActiveGridAdmin(ReadOnlyRecordAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).active()


@admin.register(DeletedGrid)
class DeletedGridAdmin(ReadOnlyRecordAdmin):
    list_display = ["grid", "deleted_by", "deleted_at"]
    list_select_related = ["grid", "deleted_by"]


admin.site.register(PreparationSession, ReadOnlyRecordAdmin)
admin.site.register(AuditEvent, ReadOnlyRecordAdmin)
