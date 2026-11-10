from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .permissions import current_staff
from .storage import change_box, register_box
from .storage_models import GridBox, GridBoxType, Puck


def pucks():
    return Puck.objects.filter(cane__name="Cane 1", cane__dewar__name="Dewar 1")


class BoxForm(forms.Form):
    name = forms.CharField(max_length=100, label="Gridbox name")
    box_type = forms.ModelChoiceField(queryset=GridBoxType.objects.all(), label="Gridbox type")
    puck = forms.ModelChoiceField(queryset=pucks(), required=False, empty_label="In stock")


class BoxActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=[
            ("move", "Place / move / return to stock"),
            ("discard", "Discard empty box"),
            ("transfer", "Transfer to another laboratory"),
        ]
    )
    puck = forms.ModelChoiceField(queryset=pucks(), required=False, empty_label="In stock")
    expected_version = forms.IntegerField(widget=forms.HiddenInput)
    transfer_destination = forms.CharField(
        required=False, max_length=200, label="Receiving laboratory / destination"
    )
    occurred_at = forms.DateTimeField(
        initial=timezone.now,
        label="Action date and time",
        help_text="Local time in Europe/Stockholm.",
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )


@login_required
def inventory(request):
    current_staff(request.user)
    form = BoxForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            box = register_box(
                actor=request.user,
                name=form.cleaned_data["name"],
                box_type_id=form.cleaned_data["box_type"].pk,
                puck_id=getattr(form.cleaned_data["puck"], "pk", None),
            )
            return redirect("registry:box_detail", pk=box.pk)
        except ValidationError as error:
            form.add_error(None, error)
    boxes = GridBox.objects.select_related("box_type", "puck")
    query = request.GET.get("q", "").strip()
    if query:
        boxes = boxes.filter(name__icontains=query)
    state = request.GET.get("state", "")
    if state not in {"", "stock", "puck", "discarded", "transferred", "all"}:
        state = ""
    if not state:
        boxes = boxes.filter(transferred_at=None, discarded=False)
    if state == "stock":
        boxes = boxes.filter(discarded=False, puck=None, transferred_at=None)
    elif state == "puck":
        boxes = boxes.filter(puck__isnull=False)
    elif state == "discarded":
        boxes = boxes.filter(discarded=True)
    elif state == "transferred":
        boxes = boxes.filter(transferred_at__isnull=False)
    return render(
        request,
        "registry/inventory.html",
        {"form": form, "boxes": boxes, "query": query, "state": state},
    )


@login_required
def box_detail(request, pk):
    current_staff(request.user)
    box = get_object_or_404(GridBox.objects.select_related("box_type", "puck"), pk=pk)
    form = BoxActionForm(
        request.POST or None, initial={"expected_version": box.version, "puck": box.puck_id}
    )
    if request.method == "POST" and form.is_valid():
        try:
            change_box(
                actor=request.user,
                box_id=pk,
                expected_version=form.cleaned_data["expected_version"],
                action=form.cleaned_data["action"],
                puck_id=getattr(form.cleaned_data["puck"], "pk", None),
                occurred_at=form.cleaned_data["occurred_at"],
                transfer_destination=form.cleaned_data["transfer_destination"],
            )
            return redirect("registry:box_detail", pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, "registry/box_detail.html", {"box": box, "form": form})
