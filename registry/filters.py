"""Typed property filters. User input can never become an arbitrary ORM lookup."""

from django import forms
from django.db.models import Q
from django.forms import BaseFormSet, formset_factory

from .grid_storage import slot_label
from .permissions import visible_grids
from .storage_models import GridBox, GridBoxType, GridSlot, Puck
from .tables import COLUMN_BY_KEY, COLUMNS


class GridPropertyFilter(forms.Form):
    property = forms.ChoiceField(
        required=False,
        choices=[("", "Choose a property")]
        + [(column["key"], column["label"]) for column in COLUMNS if column["key"] != "storage"],
    )
    contains = forms.CharField(required=False, max_length=200)
    minimum = forms.DecimalField(required=False, max_digits=30, decimal_places=10)
    maximum = forms.DecimalField(required=False, max_digits=30, decimal_places=10)
    from_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    to_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    boolean_value = forms.ChoiceField(
        required=False,
        label="Value",
        choices=[
            ("", "Choose a value"),
            ("yes", "Yes"),
            ("no", "No"),
            ("unknown", "Unknown"),
        ],
    )

    def clean(self):
        data = super().clean()
        key = data.get("property")
        if not key:
            if any(value not in (None, "") for value in data.values()):
                raise forms.ValidationError("Choose a property for this filter.")
            return data
        kind = COLUMN_BY_KEY[key]["kind"]
        if kind == "text" and not data.get("contains"):
            raise forms.ValidationError("Enter the text to find.")
        if kind in ("number", "date"):
            lower, upper = ("minimum", "maximum") if kind == "number" else ("from_date", "to_date")
            if data.get(lower) is None and data.get(upper) is None:
                raise forms.ValidationError("Enter at least one range limit.")
            if (
                data.get(lower) is not None
                and data.get(upper) is not None
                and data[lower] > data[upper]
            ):
                raise forms.ValidationError("The lower limit must not exceed the upper limit.")
        if kind == "boolean" and not data.get("boolean_value"):
            raise forms.ValidationError("Choose Yes, No or Unknown.")
        return data


class PreparationFilterSet(BaseFormSet):
    def is_valid(self):
        valid = super().is_valid()
        storage = getattr(self, "storage_filters", None)
        return (storage.is_valid() if storage is not None and storage.is_bound else True) and valid


class InventorySelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if isinstance(instance, GridBox):
            option["attrs"]["data-puck"] = instance.puck_id or ""
            option["attrs"]["data-type"] = instance.box_type_id
        elif isinstance(instance, GridSlot):
            option["attrs"]["data-box"] = instance.box_id
        return option


class StoragePropertyFilter(forms.Form):
    property = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Choose a storage property"),
            ("puck", "Puck"),
            ("box", "Gridbox"),
            ("box_type", "Gridbox type"),
            ("slot", "Slot"),
            ("clipped", "Clipped / unclipped"),
        ],
    )
    puck = forms.ModelChoiceField(queryset=Puck.objects.all(), required=False)
    box = forms.ModelChoiceField(
        queryset=GridBox.objects.all(), required=False, widget=InventorySelect
    )
    box_type = forms.ModelChoiceField(queryset=GridBoxType.objects.all(), required=False)
    slot = forms.ModelChoiceField(
        queryset=GridSlot.objects.select_related("box__box_type").all(),
        required=False,
        widget=InventorySelect,
    )
    clipped = forms.ChoiceField(
        required=False, choices=[("", "Choose a value"), ("yes", "Clipped"), ("no", "Unclipped")]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slot"].label_from_instance = lambda slot: (
            f"{slot.box.name} / {slot_label(slot)}"
        )

    def clean(self):
        values = super().clean()
        key = values.get("property")
        if key and not values.get(key):
            raise forms.ValidationError("Choose a value for this storage filter.")
        if not key and any(value for value in values.values()):
            raise forms.ValidationError("Choose a storage property.")
        return values


StorageFilterSet = formset_factory(
    StoragePropertyFilter, extra=1, max_num=20, validate_max=True, absolute_max=20
)


GridFilterSet = formset_factory(
    GridPropertyFilter,
    formset=PreparationFilterSet,
    extra=1,
    max_num=20,
    validate_max=True,
    absolute_max=20,
)


def search_registry(parameters, *, actor):
    """Use the same selection for the on-screen registry and its Excel export."""
    query = parameters.get("q", "").strip()
    grids = visible_grids(actor).select_related(
        "session__owner", "session__prepared_by", "gridslot__box__puck", "gridslot__box__box_type"
    )
    if query:
        grids = grids.filter(
            Q(grid_number__icontains=query)
            | Q(sample_description__icontains=query)
            | Q(session__owner__name__icontains=query)
            | Q(session__experiment_reference__icontains=query)
        )
    data = parameters if "filters-TOTAL_FORMS" in parameters else None
    filters = GridFilterSet(data, prefix="filters")
    storage_data = parameters if "storage-TOTAL_FORMS" in parameters else None
    storage_filters = StorageFilterSet(storage_data, prefix="storage")
    filters.storage_filters = storage_filters
    if filters.is_bound:
        if filters.is_valid():
            grids = apply_property_filters(grids, filters)
        else:
            grids = grids.none()  # Invalid input must never broaden an export.
    if storage_filters.is_bound:
        if storage_filters.is_valid():
            for rule in storage_filters.cleaned_data:
                key = rule.get("property")
                if not key:
                    continue
                lookup = {
                    "puck": "gridslot__box__puck",
                    "box": "gridslot__box",
                    "box_type": "gridslot__box__box_type",
                    "slot": "gridslot",
                    "clipped": "is_clipped",
                }[key]
                value = rule[key] if key != "clipped" else rule[key] == "yes"
                grids = grids.filter(**{lookup: value})
        else:
            grids = grids.none()
    return grids.order_by("-pk"), query, filters


def apply_property_filters(grids, filters):
    for data in filters.cleaned_data:
        key = data.get("property")
        if not key:
            continue
        column = COLUMN_BY_KEY[key]
        lookup, kind = column["lookup"], column["kind"]
        if kind == "text":
            grids = grids.filter(**{f"{lookup}__icontains": data["contains"]})
        elif kind == "boolean":
            value = {"yes": True, "no": False, "unknown": None}[data["boolean_value"]]
            grids = grids.filter(**{lookup: value})
        else:
            lower, upper = ("minimum", "maximum") if kind == "number" else ("from_date", "to_date")
            if kind == "date":
                lookup += "__date"  # Inclusive local dates; do not discard the last day's events.
            if data.get(lower) is not None:
                grids = grids.filter(**{f"{lookup}__gte": data[lower]})
            if data.get(upper) is not None:
                grids = grids.filter(**{f"{lookup}__lte": data[upper]})
    return grids
