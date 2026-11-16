from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
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
)
from .models import AuditEvent, DeletedGrid, Grid, PreparationSession
from .owner_queries import search_owners
from .permissions import can_edit_grid, current_staff, require_grid_editor
from .preparation import PREPARATION_GROUPS
from .services import (
    archive_grid,
    create_preparation_session,
    create_sample_owner,
    suggest_owner_code,
)
from .session_queries import search_sessions
from .suggestions import preparation_suggestions
from .tables import COLUMNS


class GridOutcomeForm(forms.Form):
    outcome = forms.ChoiceField(
        label="Action",
        choices=[
            ("", "Choose an action"),
            (Grid.Status.SCREENED_RECOVERED, "Screened and recovered"),
            (Grid.Status.SCREENED_DISCARDED, "Screened and discarded"),
            (Grid.Status.DISCARDED, "Discarded without screening"),
        ],
    )
    reason = forms.CharField(
        label="Discard reason (optional)",
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    expected_version = forms.IntegerField(widget=forms.HiddenInput, min_value=1)


class GridStatusCorrectionForm(forms.Form):
    password = forms.CharField(
        label="Your password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    reason = forms.CharField(
        label="Reason for correction", max_length=2000, widget=forms.Textarea(attrs={"rows": 2})
    )
    expected_version = forms.IntegerField(widget=forms.HiddenInput, min_value=1)
    event_id = forms.IntegerField(widget=forms.HiddenInput, min_value=1)


def add_service_error(form, error):
    # Service errors can include model fields that are not on this particular form.
    for message in error.messages:
        form.add_error(None, message)


@login_required
def grid_list(request):
    grids, query, filters = search_registry(request.GET, actor=request.user)
    preparation_filter_errors = bool(filters.non_form_errors()) or any(
        bool(errors) for errors in filters.errors
    )
    storage_filter_errors = bool(filters.storage_filters.non_form_errors()) or any(
        bool(errors) for errors in filters.storage_filters.errors
    )
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
            "preparation_filter_errors": preparation_filter_errors,
            "storage_filter_errors": storage_filter_errors,
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
    query, owners = search_owners(request.GET, actor=request.user)
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
    form, sessions = search_sessions(request.GET, actor=request.user)
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
                "session__owner",
                "session__prepared_by",
                "gridslot__box__puck",
                "gridslot__box__box_type",
            ),
            "deleted_count": session.grids.archived().count(),
            "columns": COLUMNS,
            "snapshot_groups": snapshot_groups,
        },
    )


@login_required
@sensitive_post_parameters("password")
def grid_detail(request, pk):
    current_staff(request.user)
    grid = get_object_or_404(Grid.objects.active().select_related("session__owner"), pk=pk)
    can_edit = can_edit_grid(request.user, grid)
    if request.method == "POST":
        require_grid_editor(request.user, grid)
    outcome_post = request.method == "POST" and request.POST.get("intent") == "outcome"
    correction_post = request.method == "POST" and request.POST.get("intent") == "correct_status"
    latest_event = grid.physical_events.order_by("-pk").first()
    can_correct_status = bool(
        latest_event
        and latest_event.operation in {"screened", "discarded"}
        and grid.status
        in {Grid.Status.SCREENED_RECOVERED, Grid.Status.DISCARDED, Grid.Status.SCREENED_DISCARDED}
    )
    correction_form = GridStatusCorrectionForm(
        request.POST if correction_post else None,
        initial={
            "expected_version": grid.version,
            "event_id": latest_event.pk if latest_event else None,
        },
    )
    if correction_post and correction_form.is_valid():
        from .grid_storage import correct_grid_outcome

        try:
            correct_grid_outcome(
                actor=request.user, grid_id=grid.pk, **correction_form.cleaned_data
            )
        except ValidationError as error:
            add_service_error(correction_form, error)
        else:
            messages.success(
                request, "Grid status corrected; the original action remains in history."
            )
            return redirect("registry:grid_detail", pk=grid.pk)
    outcome_form = GridOutcomeForm(
        request.POST if outcome_post else None, initial={"expected_version": grid.version}
    )
    if grid.status == Grid.Status.SCREENED_RECOVERED:
        outcome_form.fields["outcome"].choices = [
            ("", "Choose an action"),
            (Grid.Status.DISCARDED, "Discard grid"),
        ]
    if outcome_post and outcome_form.is_valid():
        from .grid_storage import record_grid_outcome

        try:
            record_grid_outcome(actor=request.user, grid_id=grid.pk, **outcome_form.cleaned_data)
        except ValidationError as error:
            add_service_error(outcome_form, error)
        else:
            messages.success(request, "Grid status recorded.")
            return redirect("registry:grid_detail", pk=grid.pk)
    form = EditGridForm(
        request.POST
        if request.method == "POST" and not outcome_post and not correction_post
        else None,
        instance=grid,
        initial={"expected_version": grid.version},
    )
    if request.method == "POST" and not outcome_post and not correction_post and form.is_valid():
        try:
            from .grid_storage import save_preparation_and_clipping

            saved, location_released = save_preparation_and_clipping(
                clipped=form.cleaned_data["is_clipped"],
                actor=request.user,
                grid_id=grid.pk,
                preparation=form.preparation_values(),
                expected_version=form.cleaned_data["expected_version"],
            )
        except ValidationError as error:
            add_service_error(form, error)
        else:
            messages.success(request, "Grid preparation saved. Other grids were not changed.")
            if location_released:
                messages.warning(
                    request,
                    "Clipping status changed. The previous slot is incompatible. "
                    "Storage is now Unknown — needs review.",
                )
            return redirect("registry:grid_detail", pk=grid.pk)
    for field in form.fields.values():
        field.widget.attrs["form"] = "grid-preparation-form"
    audit = AuditEvent.objects.filter(entity_type="Grid", entity_id=str(grid.pk)).select_related(
        "actor"
    )
    return render(
        request,
        "registry/grid_detail.html",
        {
            "grid": grid,
            "form": form,
            "outcome_form": outcome_form,
            "correction_form": correction_form,
            "can_correct_status": can_correct_status,
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
def discarded_grid_list(request):
    current_staff(request.user)
    form = DeletedGridBrowseForm(request.GET)
    form.fields["q"].label = "Search discarded grids"
    discarded = (
        Grid.objects.active()
        .filter(status__in=[Grid.Status.DISCARDED, Grid.Status.SCREENED_DISCARDED])
        .select_related("session__owner")
        .prefetch_related("physical_events__actor")
    )
    if form.is_valid():
        query = form.cleaned_data["q"]
        if query:
            discarded = discarded.filter(
                Q(grid_number__icontains=query) | Q(session__owner__name__icontains=query)
            )
        if form.cleaned_data["session"]:
            discarded = discarded.filter(session_id=form.cleaned_data["session"])
    else:
        discarded = discarded.none()
    parameters = request.GET.copy()
    parameters.pop("page", None)
    page = Paginator(discarded.order_by("-pk"), 50).get_page(request.GET.get("page"))
    for grid in page:
        grid.discard_event = next(
            (event for event in grid.physical_events.all() if event.operation == "discarded"), None
        )
    return render(
        request,
        "registry/discarded_grid_list.html",
        {
            "form": form,
            "page": page,
            "filter_query": parameters.urlencode(),
        },
    )


@login_required
@require_GET
def transferred_grid_list(request):
    current_staff(request.user)
    form = DeletedGridBrowseForm(request.GET)
    form.fields["q"].label = "Search transferred grids"
    grids = (
        Grid.objects.active()
        .filter(status=Grid.Status.TRANSFERRED)
        .select_related("session__owner", "gridslot__box__box_type")
    )
    if form.is_valid():
        query = form.cleaned_data["q"]
        if query:
            grids = grids.filter(
                Q(grid_number__icontains=query)
                | Q(session__owner__name__icontains=query)
                | Q(gridslot__box__name__icontains=query)
                | Q(gridslot__box__transfer_destination__icontains=query)
            )
        if form.cleaned_data["session"]:
            grids = grids.filter(session_id=form.cleaned_data["session"])
    else:
        grids = grids.none()
    parameters = request.GET.copy()
    parameters.pop("page", None)
    return render(
        request,
        "registry/transferred_grid_list.html",
        {
            "form": form,
            "page": Paginator(grids.order_by("-pk"), 50).get_page(request.GET.get("page")),
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
