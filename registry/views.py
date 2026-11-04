from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Value
from django.db.models.functions import Concat
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods

from .filters import search_registry
from .forms import (
    DeletedGridBrowseForm,
    DeleteGridForm,
    EditGridForm,
    NewSessionForm,
    OwnerNameForm,
    OwnerRegistrationForm,
    PreparationForm,
    SessionBrowseForm,
)
from .models import AuditEvent, DeletedGrid, Grid, PreparationSession
from .permissions import can_edit_grid, current_staff, require_grid_editor, visible_owners
from .preparation import PREPARATION_GROUPS
from .services import (
    archive_grid,
    create_preparation_session,
    create_sample_owner,
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
    grids, query, filters = search_registry(request.GET)
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
def owner_list(request):
    owners = visible_owners(request.user)
    query = request.GET.get("q", "").strip()
    if query:
        owners = owners.filter(
            Q(name__icontains=query) | Q(code__icontains=query) | Q(affiliation__icontains=query)
        )
    page = Paginator(owners, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "registry/owner_list.html",
        {
            "page": page,
            "query": query,
        },
    )


@login_required
def new_owner(request):
    actor = current_staff(request.user)
    saving = request.method == "POST" and request.POST.get("action") == "save"
    reviewing = request.method == "POST" and (saving or "affiliation" in request.POST)
    form = OwnerRegistrationForm(request.POST) if reviewing else OwnerNameForm(request.POST or None)
    proposed_code = None
    if request.method == "POST" and form.is_valid():
        try:
            if saving:
                owner = create_sample_owner(
                    actor=actor,
                    name=form.cleaned_data["name"],
                    affiliation=form.cleaned_data["affiliation"],
                    notes=form.cleaned_data["notes"],
                    preferred_code=form.cleaned_data.get("owner_code_preview", ""),
                )
                messages.success(request, f"Sample owner registered with code {owner.code}.")
                return redirect(f"{reverse('registry:new_session')}?owner={owner.pk}")
            proposed_code = suggest_owner_code(form.cleaned_data["name"])
            if not reviewing:
                form = OwnerRegistrationForm(initial={"name": form.cleaned_data["name"]})
            reviewing = True
        except ValidationError as error:
            add_service_error(form, error)
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
def session_list(request):
    current_staff(request.user)
    form = SessionBrowseForm(request.GET, actor=request.user)
    sessions = PreparationSession.objects.select_related("owner", "prepared_by").annotate(
        grid_count=Count("grids", filter=Q(grids__deletion__isnull=True)),
        deleted_count=Count("grids", filter=Q(grids__deletion__isnull=False)),
        operator_name=Concat("prepared_by__first_name", Value(" "), "prepared_by__last_name"),
    )
    if form.is_valid():
        data = form.cleaned_data
        query = data["q"]
        if query:
            matches = (
                Q(owner__name__icontains=query)
                | Q(owner__code__icontains=query)
                | Q(prepared_by__username__icontains=query)
                | Q(operator_name__icontains=query)
                | Q(experiment_reference__icontains=query)
                | Q(project_reference__icontains=query)
            )
            number = query.lower().removeprefix("session ").strip()
            if number.isascii() and number.isdigit() and len(number) <= 18:
                matches |= Q(pk=int(number))
            sessions = sessions.filter(matches)
        if data["owner"]:
            sessions = sessions.filter(owner=data["owner"])
        if data["from_date"]:
            sessions = sessions.filter(prepared_at__date__gte=data["from_date"])
        if data["to_date"]:
            sessions = sessions.filter(prepared_at__date__lte=data["to_date"])
    else:
        sessions = sessions.none()
    parameters = request.GET.copy()
    parameters.pop("page", None)
    page = Paginator(sessions.order_by("-pk"), 50).get_page(request.GET.get("page"))
    return render(
        request,
        "registry/session_list.html",
        {
            "form": form,
            "page": page,
            "filter_query": parameters.urlencode(),
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
            "grids": session.grids.active().select_related(
                "session__owner", "session__prepared_by"
            ),
            "deleted_count": session.grids.archived().count(),
            "columns": COLUMNS,
            "snapshot_groups": snapshot_groups,
        },
    )


@login_required
def grid_detail(request, pk):
    current_staff(request.user)
    grid = get_object_or_404(Grid.objects.active().select_related("session__owner"), pk=pk)
    can_edit = can_edit_grid(request.user, grid)
    if request.method == "POST":
        require_grid_editor(request.user, grid)
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


@login_required
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters("password")
def grid_delete(request, pk):
    current_staff(request.user)
    grid = get_object_or_404(Grid.objects.select_related("session__owner"), pk=pk)
    if request.method == "GET" and DeletedGrid.objects.filter(grid=grid).exists():
        return redirect("registry:deleted_grid_detail", pk=grid.pk)
    form = DeleteGridForm(request.POST or None, initial={"expected_version": grid.version})
    if request.method == "POST" and form.is_valid():
        try:
            archive_grid(
                actor=request.user,
                grid_id=grid.pk,
                password=form.cleaned_data["password"],
                expected_version=form.cleaned_data["expected_version"],
            )
        except ValidationError as error:
            add_service_error(form, error)
        else:
            messages.success(request, f"{grid.grid_number} was moved to Deleted grids.")
            return redirect("registry:grid_list")
    return render(request, "registry/grid_delete.html", {"grid": grid, "form": form})


@login_required
@require_GET
def deleted_grid_list(request):
    current_staff(request.user)
    form = DeletedGridBrowseForm(request.GET)
    deleted = DeletedGrid.objects.select_related("grid__session__owner", "deleted_by")
    if form.is_valid():
        query = form.cleaned_data["q"]
        if query:
            deleted = deleted.filter(
                Q(grid__grid_number__icontains=query)
                | Q(grid__session__owner__name__icontains=query)
                | Q(deleted_by__username__icontains=query)
            )
        if form.cleaned_data["session"]:
            deleted = deleted.filter(grid__session_id=form.cleaned_data["session"])
    else:
        deleted = deleted.none()
    parameters = request.GET.copy()
    parameters.pop("page", None)
    page = Paginator(deleted, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "registry/deleted_grid_list.html",
        {
            "form": form,
            "page": page,
            "filter_query": parameters.urlencode(),
        },
    )


@login_required
@require_GET
def deleted_grid_detail(request, pk):
    current_staff(request.user)
    deleted = get_object_or_404(
        DeletedGrid.objects.select_related("grid__session__owner", "deleted_by"), grid_id=pk
    )
    audit = AuditEvent.objects.filter(entity_type="Grid", entity_id=str(pk)).select_related("actor")
    return render(
        request,
        "registry/deleted_grid_detail.html",
        {
            "deleted": deleted,
            "grid": deleted.grid,
            "form": PreparationForm(instance=deleted.grid),
            "audit": audit,
        },
    )
