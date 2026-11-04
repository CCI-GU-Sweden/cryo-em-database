"""Typed property filters. User input can never become an arbitrary ORM lookup."""

from django import forms
from django.forms import formset_factory

from .tables import COLUMN_BY_KEY, COLUMNS


class GridPropertyFilter(forms.Form):
    property = forms.ChoiceField(
        required=False,
        choices=[("", "Choose a property")]
        + [(column["key"], column["label"]) for column in COLUMNS],
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


GridFilterSet = formset_factory(
    GridPropertyFilter, extra=1, max_num=20, validate_max=True, absolute_max=20
)


def apply_property_filters(grids, filters):
    for data in filters.cleaned_data:
        key = data.get("property")
        if not key:
            continue
        column = COLUMN_BY_KEY[key]
        lookup, kind = column["lookup"], column["kind"]
        if key == "storage":
            if data["contains"].casefold() not in "unassigned":
                grids = grids.none()
        elif kind == "text":
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
