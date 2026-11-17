from django import template
from django.utils import timezone

from cci_grids.preparation import compact_decimal
from cci_grids.tables import COLUMN_BY_KEY

register = template.Library()


@register.inclusion_tag("registry/storage_links.html")
def storage_links(grid):
    from cci_grids.grid_storage import discard_location, slot_label

    slot = getattr(grid, "gridslot", None)
    return {
        "slot": slot,
        "label": slot_label(slot) if slot else None,
        "discarded": discard_location(grid),
    }


@register.filter
def column_value(grid, key):
    column = COLUMN_BY_KEY[key]
    if key == "status":
        if grid.status == grid.Status.TRANSFERRED:
            slot = getattr(grid, "gridslot", None)
            if slot and slot.box.transfer_destination:
                return f"Transferred to {slot.box.transfer_destination}"
        return grid.get_status_display()
    if key == "storage":
        from cci_grids.grid_storage import location

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
