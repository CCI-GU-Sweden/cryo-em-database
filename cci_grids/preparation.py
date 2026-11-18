"""Explicit list of editable preparation fields shared by forms and services.

JSON snapshots encode Decimal values as strings to preserve precision. The grid
itself stores numeric values in decimal columns, so later sorting stays numeric.
"""

from decimal import Decimal

PREPARATION_GROUPS = [
    (
        "Sample",
        [
            "sample_description",
            "sample_concentration_value",
            "sample_concentration_unit",
            "buffer_description",
        ],
    ),
    (
        "Grid and carbon",
        [
            "grid_type",
            "grid_box_number",
            "carbon_description",
            "carbon_thickness_nm",
            "carbon_thickness_layers",
        ],
    ),
    (
        "Glow discharge",
        ["glow_device", "glow_atmosphere", "glow_polarity", "glow_current_ma", "glow_duration_s"],
    ),
    (
        "Freezing and blotting",
        [
            "freezing_device",
            "sample_volume_ul",
            "temperature_c",
            "humidity_percent",
            "blot_time_s",
            "hold_time_s",
            "drain_time_s",
            "blot_force",
            "multiple_blot",
        ],
    ),
    ("Grid notes", ["notes"]),
]
PREPARATION_FIELDS = [name for _, names in PREPARATION_GROUPS for name in names]


def compact_decimal(value):
    """Show 3 instead of 3.000 while keeping meaningful digits and zero."""
    if not isinstance(value, Decimal):
        return value
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def preparation_snapshot(grid):
    values = {}
    for name in PREPARATION_FIELDS:
        value = getattr(grid, name)
        values[name] = str(value) if isinstance(value, Decimal) else value
    return values


def normalize_preparation_text(field_name, value):
    if not isinstance(value, str):
        return value
    if field_name in ("glow_device", "freezing_device"):
        value = value.strip()
        return "" if value.casefold() == "unknown" else value
    if field_name == "carbon_description":
        return value.strip().casefold()
    if field_name in ("glow_atmosphere", "glow_polarity"):
        return value.strip().title()
    return value
