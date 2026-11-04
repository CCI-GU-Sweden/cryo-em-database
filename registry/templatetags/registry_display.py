from django import template
from django.utils import timezone

from registry.preparation import compact_decimal
from registry.tables import COLUMN_BY_KEY

register = template.Library()


@register.filter
def column_value(grid, key):
    column = COLUMN_BY_KEY[key]
    if key == "storage":
        return "Unassigned"
    value = grid
    for attribute in column["lookup"].split("__"):
        value = getattr(value, attribute, None)
        if value is None:
            return "Unknown" if column["kind"] == "boolean" else "—"
    if column["kind"] == "boolean":
        return "Yes" if value else "No"
    if column["kind"] == "date":
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
    return compact_decimal(value) if value != "" else "—"
