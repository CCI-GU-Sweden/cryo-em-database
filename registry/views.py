from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .filters import GridFilterSet, apply_property_filters
from .forms import EditGridForm, NewSessionForm, OwnerNameForm, OwnerRegistrationForm
from .models import AuditEvent, Grid, PreparationSession
from .permissions import current_staff, editable_owners, require_editor
from .preparation import PREPARATION_GROUPS
from .services import (
    create_preparation_session,
    save_administration_record,
    suggest_owner_code,
    update_grid_preparation,
)
from .suggestions import preparation_suggestions
from .tables import COLUMNS


def add_service_error(form, error):
    # Service errors can include model fields that are not on this particular form.
    for message in error.messages:
        form.add_error(None, message)


@login_required
def grid_list(request):
    current_staff(request.user)
    query = request.GET.get("q", "").strip()
    grids = Grid.objects.select_related("session__owner", "session__prepared_by")
    if query:
        grids = grids.filter(
            Q(grid_number__icontains=query)
            | Q(sample_description__icontains=query)
            | Q(session__owner__name__icontains=query)
            | Q(session__experiment_reference__icontains=query)
        )
    filter_data = request.GET if "filters-TOTAL_FORMS" in request.GET else None
    filters = GridFilterSet(filter_data, prefix="filters")
    if filters.is_bound:
        if filters.is_valid():
            grids = apply_property_filters(grids, filters)
        else:
            grids = grids.none()  # Invalid ranges must never silently broaden results.
    parameters = request.GET.copy()
    parameters.pop("page", None)
    page = Paginator(grids.order_by("-pk"), 50).get_page(request.GET.get("page"))
    return render(
        request,
        "registry/grid_list.html",
        {
            "page": page,
            "query": query,
            "columns": COLUMNS,
            "filters": filters,
            "filter_query": parameters.urlencode(),
            "filter_kinds": {column["key"]: column["kind"] for column in COLUMNS},
        },
    )


@login_required
def new_session(request):
    current_staff(request.user)
    form = NewSessionForm(
        request.POST or None, actor=request.user, initial={"owner": request.GET.get("owner")}
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            session = create_preparation_session(
                actor=request.user,
                owner=data["owner"],
                prepared_at=data["prepared_at"],
                grid_count=data["grid_count"],
                preparation=form.preparation_values(),
                request_token=data["request_token"],
                experiment_reference=data["experiment_reference"],
                project_reference=data["project_reference"],
                notes=data["session_notes"],
            )
        except ValidationError as error:
            add_service_error(form, error)
        else:
            messages.success(
                request, "Preparation session saved. Each grid can now be edited separately."
            )
            return redirect("registry:session_detail", pk=session.pk)
    return render(
        request,
        "registry/new_session.html",
        {
            "form": form,
            "preparation_suggestions": preparation_suggestions(),
        },
    )


@login_required
def new_owner(request):
    actor = current_staff(request.user)
    if not actor.is_superuser:
        raise PermissionDenied("Only an administrator can register sample owners.")
    saving = request.method == "POST" and request.POST.get("action") == "save"
    reviewing = request.method == "POST" and (saving or "affiliation" in request.POST)
    form = OwnerRegistrationForm(request.POST) if reviewing else OwnerNameForm(request.POST or None)
    proposed_code = None
    if request.method == "POST" and form.is_valid():
        proposed_code = suggest_owner_code(form.cleaned_data["name"])
        if saving:
            owner = save_administration_record(
                actor=actor,
                instance=form.save(commit=False),
                preferred_code=form.cleaned_data.get("owner_code_preview", ""),
            )
            messages.success(request, f"Sample owner registered with code {owner.code}.")
            return redirect(f"{reverse('registry:new_session')}?owner={owner.pk}")
        if not reviewing:
            form = OwnerRegistrationForm(initial={"name": form.cleaned_data["name"]})
        reviewing = True
    return render(
        request,
        "registry/new_owner.html",
        {
            "form": form,
            "reviewing": reviewing,
            "proposed_code": proposed_code,
        },
    )


@login_required
def session_detail(request, pk):
    current_staff(request.user)
    session = get_object_or_404(
        PreparationSession.objects.select_related("owner", "prepared_by"), pk=pk
    )
    snapshot_groups = [
        (
            title,
            [
                (Grid._meta.get_field(name).verbose_name, session.defaults.get(name))
                for name in names
            ],
        )
        for title, names in PREPARATION_GROUPS
    ]
    return render(
        request,
        "registry/session_detail.html",
        {
            "session": session,
            "grids": session.grids.select_related("session__owner", "session__prepared_by"),
            "columns": COLUMNS,
            "snapshot_groups": snapshot_groups,
        },
    )


@login_required
def grid_detail(request, pk):
    current_staff(request.user)
    grid = get_object_or_404(Grid.objects.select_related("session__owner"), pk=pk)
    can_edit = editable_owners(request.user).filter(pk=grid.session.owner_id).exists()
    if request.method == "POST":
        require_editor(request.user, grid.session.owner)
    form = EditGridForm(
        request.POST or None, instance=grid, initial={"expected_version": grid.version}
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_grid_preparation(
                actor=request.user,
                grid_id=grid.pk,
                preparation=form.preparation_values(),
                expected_version=form.cleaned_data["expected_version"],
            )
        except ValidationError as error:
            add_service_error(form, error)
        else:
            messages.success(request, "Grid preparation saved. Other grids were not changed.")
            return redirect("registry:grid_detail", pk=grid.pk)
    audit = AuditEvent.objects.filter(entity_type="Grid", entity_id=str(grid.pk)).select_related(
        "actor"
    )
    return render(
        request,
        "registry/grid_detail.html",
        {
            "grid": grid,
            "form": form,
            "can_edit": can_edit,
            "preparation_suggestions": preparation_suggestions() if can_edit else {},
            "audit": audit,
        },
    )
