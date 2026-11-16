"""Explicit registry columns double as the safe allowlist for property filters."""

from django.db import models

from .forms import PreparationForm
from .models import Grid
from .preparation import PREPARATION_FIELDS

COLUMNS = [
    {"key": "grid_number", "label": "Grid ID", "lookup": "grid_number", "kind": "text"},
    {"key": "owner", "label": "Sample owner", "lookup": "session__owner__name", "kind": "text"},
    {"key": "owner_code", "label": "Owner code", "lookup": "session__owner__code", "kind": "text"},
    {
        "key": "prepared_by",
        "label": "Operator (login)",
        "lookup": "session__prepared_by__username",
        "kind": "text",
    },
    {
        "key": "prepared_at",
        "label": "Preparation date",
        "lookup": "session__prepared_at",
        "kind": "date",
    },
    {
        "key": "experiment_reference",
        "label": "Experiment reference",
        "lookup": "session__experiment_reference",
        "kind": "text",
    },
    {
        "key": "project_reference",
        "label": "Project reference",
        "lookup": "session__project_reference",
        "kind": "text",
    },
    {"key": "session_notes", "label": "Session notes", "lookup": "session__notes", "kind": "text"},
    {"key": "created_at", "label": "Recorded at", "lookup": "created_at", "kind": "date"},
]
for name in PREPARATION_FIELDS:
    field = Grid._meta.get_field(name)
    kind = "number" if isinstance(field, (models.DecimalField, models.IntegerField)) else "text"
    if isinstance(field, models.BooleanField):
        kind = "boolean"
    COLUMNS.append(
        {
            "key": name,
            "label": {
                "glow_device": "Glow discharge device",
                "freezing_device": "Freezing device",
            }.get(
                name, PreparationForm.Meta.labels.get(name, str(field.verbose_name).capitalize())
            ),
            "lookup": name,
            "kind": kind,
        }
    )
COLUMNS.append({"key": "status", "label": "Status", "lookup": "status", "kind": "text"})
COLUMNS.append({"key": "storage", "label": "Storage", "lookup": None, "kind": "text"})
DEFAULT_COLUMNS = {
    "grid_number",
    "sample_description",
    "sample_concentration_value",
    "sample_concentration_unit",
    "blot_time_s",
    "owner",
    "storage",
}
for column in COLUMNS:
    column["visible"] = column["key"] in DEFAULT_COLUMNS
COLUMN_BY_KEY = {column["key"]: column for column in COLUMNS}
