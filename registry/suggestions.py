"""Suggestions combine the private seed vocabulary with actual saved grid values."""

from .models import Grid, PreparationSuggestion
from .preparation import PREPARATION_FIELDS, compact_decimal, normalize_preparation_text


def preparation_suggestions():
    suggestions = {}
    for name in PREPARATION_FIELDS:
        seeded = PreparationSuggestion.objects.filter(field_name=name).values_list(
            "value", flat=True
        )
        saved = Grid.objects.order_by().values_list(name, flat=True).distinct()
        values = {
            str(compact_decimal(normalize_preparation_text(name, value)))
            for value in [*seeded, *saved]
            if value is not None and value != ""
        }
        suggestions[name] = sorted(values, key=str.casefold)
    return suggestions
