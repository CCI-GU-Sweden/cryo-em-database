from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters

from .event_time import current_action_time
from .permissions import current_staff
from .storage import change_box, correct_last_box_action, register_box
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
        initial=current_action_time,
        label="Action date and time",
        help_text="Local time in Europe/Stockholm.",
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M:%S", attrs={"type": "datetime-local", "step": "1"}
        ),
    )


class BoxCorrectionForm(forms.Form):
    password = forms.CharField(
        label="Your password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
    expected_version = forms.IntegerField(widget=forms.HiddenInput)
    event_id = forms.IntegerField(widget=forms.HiddenInput)


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
    boxes = GridBox.objects.select_related("box_type", "puck").annotate(
        total_slots=Count("slots"),
        occupied_slots=Count("slots", filter=Q(slots__grid__isnull=False)),
    )
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
@sensitive_post_parameters("password")
def box_detail(request, pk):
    current_staff(request.user)
    box = get_object_or_404(GridBox.objects.select_related("box_type", "puck"), pk=pk)
    correcting = request.method == "POST" and request.POST.get("intent") == "correct"
    latest = box.events.first()
    correction_form = BoxCorrectionForm(
        request.POST if correcting else None,
        initial={"expected_version": box.version, "event_id": latest.pk if latest else None},
    )
    if correcting and correction_form.is_valid():
        try:
            correct_last_box_action(actor=request.user, box_id=pk, **correction_form.cleaned_data)
            return redirect("registry:box_detail", pk=pk)
        except ValidationError as error:
            correction_form.add_error(None, error)
    form = BoxActionForm(
        request.POST if request.method == "POST" and not correcting else None,
        initial={"expected_version": box.version, "puck": box.puck_id},
    )
    if request.method == "POST" and not correcting and form.is_valid():
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
    return render(
        request,
        "registry/box_detail.html",
        {
            "box": box,
            "form": form,
            "correction_form": correction_form,
            "can_correct": latest and latest.operation in {"move", "discard", "transfer"},
        },
    )


@login_required
@sensitive_post_parameters("password")
def puck_inventory(request):
    from .storage import register_puck

    current_staff(request.user)
    form = PuckRegistrationForm(request.POST if request.method == "POST" else None)
    if form.is_bound and form.is_valid():
        try:
            register_puck(actor=request.user, **form.cleaned_data)
            return redirect("registry:puck_inventory")
        except ValidationError as error:
            form.add_error(None, error)
    inventory = (
        pucks()
        .annotate(
            occupied_spaces=Count("gridbox", distinct=True),
            grid_count=Count("gridbox__slots__grid"),
        )
        .order_by("color")
    )
    return render(request, "registry/puck_inventory.html", {"pucks": inventory, "form": form})


class PuckRegistrationForm(forms.Form):
    name = forms.CharField(max_length=40, label="Puck name / colour")
    password = forms.CharField(
        label="Your password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


@login_required
def puck_detail(request, pk):
    current_staff(request.user)
    puck = get_object_or_404(pucks(), pk=pk)
    boxes = (
        GridBox.objects.filter(puck=puck)
        .select_related("box_type")
        .annotate(
            total_slots=Count("slots"),
            occupied_slots=Count("slots", filter=Q(slots__grid__isnull=False)),
        )
    )
    return render(request, "registry/puck_detail.html", {"puck": puck, "boxes": boxes})
