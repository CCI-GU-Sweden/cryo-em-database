from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .event_time import current_action_time
from .grid_storage import location, place_grid, slot_label
from .models import Grid
from .permissions import require_grid_editor
from .storage import register_box
from .storage_models import GridBox, GridSlot
from .storage_views import BoxForm, pucks


class PlacementForm(forms.Form):
    puck = forms.ModelChoiceField(
        queryset=pucks().annotate(box_count=Count("gridbox")).filter(box_count__lt=12),
        label="Place this box in puck",
        help_text="This box is currently in stock.",
    )
    slot = forms.ModelChoiceField(queryset=GridSlot.objects.none(), label="Available slot")
    occurred_at = forms.DateTimeField(
        initial=current_action_time,
        label="Action date and time",
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M:%S", attrs={"type": "datetime-local", "step": "1"}
        ),
        help_text="Europe/Stockholm",
    )
    expected_version = forms.IntegerField(widget=forms.HiddenInput)


@login_required
def grid_storage(request, pk):
    grid = get_object_or_404(Grid.objects.select_related("session"), pk=pk)
    require_grid_editor(request.user, grid)
    inline = request.GET.get("inline") == "1"
    data = request.POST if request.method == "POST" else request.GET
    clipped = grid.is_clipped or data.get("clipped") == "1"
    side = "clipped" if clipped else "unclipped"
    boxes = (
        GridBox.objects.filter(
            discarded=False,
            transferred_at=None,
            box_type__layout__has_key=side,
            slots__side=side,
            slots__grid__isnull=True,
        )
        .select_related("box_type", "puck")
        .distinct()
    )
    query = data.get("box_name", "").strip()
    choices = boxes
    box = boxes.filter(pk=data.get("box")).first() if str(data.get("box", "")).isdigit() else None
    if query:
        box = boxes.filter(name__iexact=query).first()
    selection_error = ""
    if query and box is None:
        requested = GridBox.objects.select_related("box_type").filter(name__iexact=query).first()
        if requested and side not in requested.box_type.layout:
            selection_error = (
                f"{requested.name} is {requested.box_type.name} and cannot accept a {side} grid. "
                "Choose a compatible box."
            )
        else:
            selection_error = (
                "Choose a registered CCI box with a free compatible slot, "
                "or register a new box below."
            )
    new_form = BoxForm(
        request.POST if data.get("intent") == "new_box" else None,
        auto_id="new_box_%s" if inline else "id_%s",
    )
    new_form.fields["puck"].queryset = (
        pucks().annotate(box_count=Count("gridbox")).filter(box_count__lt=12)
    )
    new_form.fields["box_type"].queryset = new_form.fields["box_type"].queryset.filter(
        layout__has_key=side
    )
    if request.method == "POST" and data.get("intent") == "new_box" and new_form.is_valid():
        try:
            box = register_box(
                actor=request.user,
                name=new_form.cleaned_data["name"],
                box_type_id=new_form.cleaned_data["box_type"].pk,
                puck_id=getattr(new_form.cleaned_data["puck"], "pk", None),
            )
            return redirect(
                f"{request.path}?box={box.pk}&clipped={int(clipped)}"
                + ("&inline=1" if inline else "")
            )
        except ValidationError as error:
            new_form.add_error(None, error)
    form = PlacementForm(
        request.POST if request.method == "POST" and data.get("intent") == "place" else None,
        initial={"expected_version": grid.version},
        auto_id="storage_%s" if inline else "id_%s",
    )
    slots = (
        GridSlot.objects.filter(box=box, side=side).filter(grid=None)
        if box
        else GridSlot.objects.none()
    )
    form.fields["slot"].queryset = slots.select_related("box__box_type")
    if box is None or box.puck_id:
        form.fields.pop("puck")
    form.fields["slot"].label_from_instance = slot_label
    if form.is_bound and form.is_valid():
        try:
            place_grid(
                actor=request.user,
                grid_id=grid.pk,
                slot_id=form.cleaned_data["slot"].pk,
                clipped=clipped,
                expected_version=form.cleaned_data["expected_version"],
                occurred_at=form.cleaned_data["occurred_at"],
                puck_id=getattr(form.cleaned_data.get("puck"), "pk", None),
            )
            if inline:
                return redirect(f"{request.path}?inline=1&placed=1")
            return redirect("registry:session_detail", pk=grid.session_id)
        except ValidationError as error:
            form.add_error(None, error)
    return render(
        request,
        "registry/grid_storage_panel.html" if inline else "registry/grid_storage.html",
        {
            "grid": grid,
            "placed": request.GET.get("placed") == "1",
            "location": location(grid),
            "clipped": clipped,
            "boxes": choices,
            "box": box,
            "query": query,
            "form": form,
            "new_form": new_form,
            "selection_error": selection_error,
        },
    )
