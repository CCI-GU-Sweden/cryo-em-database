"""Staff Excel downloads and a two-step upload/confirmation workflow."""

import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .excel import export_workbook, read_workbook
from .excel_import import import_workbook, preview_import
from .filters import search_registry
from .forms import ExcelImportForm
from .models import Grid
from .permissions import require_grid_importer

PREVIEW_SESSION_KEY = "registry_excel_preview"
PREVIEW_LIFETIME_SECONDS = 20 * 60


def _download(content, filename):
    response = HttpResponse(
        content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_GET
def excel_template(request):
    require_grid_importer(request.user)
    content = export_workbook(actor=request.user, grids=Grid.objects.none())
    return _download(content, "cci-grid-import-template.xlsx")


@login_required
@require_GET
def excel_export(request):
    grids, _, filters = search_registry(request.GET, actor=request.user)
    if filters.is_bound and not filters.is_valid():
        return HttpResponse("Correct the registry filters before exporting.", status=400)
    try:
        content = export_workbook(actor=request.user, grids=grids)
    except ValidationError as error:
        return HttpResponse(" ".join(error.messages), status=400, content_type="text/plain")
    date = timezone.localdate().strftime("%Y%m%d")
    return _download(content, f"cci-grids-{date}.xlsx")


@login_required
@require_http_methods(["GET", "POST"])
def excel_import(request):
    require_grid_importer(request.user)
    form = ExcelImportForm()
    report, preview_token = None, None
    errors = []
    if request.method == "POST":
        action = request.POST.get("action", "preview")
        if action == "cancel":
            request.session.pop(PREVIEW_SESSION_KEY, None)
            return redirect("registry:grid_list")
        if action == "confirm":
            preview = request.session.pop(PREVIEW_SESSION_KEY, None)
            valid = (
                preview
                and preview["actor_id"] == request.user.pk
                and secrets.compare_digest(preview["token"], request.POST.get("preview_token", ""))
                and timezone.now().timestamp() - preview["created_at"] <= PREVIEW_LIFETIME_SECONDS
            )
            if not valid:
                errors = ["Upload and preview the workbook again before confirming."]
            else:
                try:
                    result = import_workbook(actor=request.user, payload=preview["payload"])
                except ValidationError as error:
                    errors = error.messages
                else:
                    messages.success(
                        request,
                        f"Import complete: {result['new_grids']} new grids, "
                        f"{result['existing_grids']} already present, "
                        f"{result['skipped_rows']} blank rows skipped.",
                    )
                    return redirect("registry:grid_list")
        else:
            request.session.pop(PREVIEW_SESSION_KEY, None)
            form = ExcelImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    file = form.cleaned_data["workbook"]
                    payload = read_workbook(file, filename=file.name)
                    report = preview_import(actor=request.user, payload=payload)
                except ValidationError as error:
                    form.add_error(None, error)
                else:
                    preview_token = secrets.token_hex(24)
                    request.session[PREVIEW_SESSION_KEY] = {
                        "actor_id": request.user.pk,
                        "token": preview_token,
                        "created_at": timezone.now().timestamp(),
                        "payload": payload,
                    }
    return render(
        request,
        "registry/excel_import.html",
        {
            "form": form,
            "report": report,
            "preview_token": preview_token,
            "errors": errors,
        },
    )
