from django import template
from django.utils import timezone

from registry.preparation import compact_decimal
from registry.tables import COLUMN_BY_KEY

register = template.Library()


@register.filter
def column_value(grid, key):
    column = COLUMN_BY_KEY[key]
    if key == "storage":
        from registry.grid_storage import location

        return location(grid)
    value = grid
    for attribute in column["lookup"].split("__"):
        value = getattr(value, attribute, None)
        if value is None:
            return "Unknown" if column["kind"] == "boolean" else "—"
    if column["kind"] == "boolean":
        return "Yes" if value else "No"
    if column["kind"] == "date":
        format_string = "%Y-%m-%d" if key == "prepared_at" else "%Y-%m-%d %H:%M"
        return timezone.localtime(value).strftime(format_string)
    if value == "" and key in {"glow_device", "freezing_device", "carbon_description"}:
        return "Unknown"
    return compact_decimal(value) if value != "" else "—"
