"""Facility-local dates without changing the host application's time zone."""

from functools import wraps
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

FACILITY_TIMEZONE = ZoneInfo("Europe/Stockholm")


def facility_view(view):
    """Keep form parsing, queries and response rendering in facility local time."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        request.cci_grids_base_template = (
            "base.html"
            if getattr(settings, "CCI_GRIDS_DASHBOARD", False)
            else "registry/standalone_base.html"
        )
        with timezone.override(FACILITY_TIMEZONE):
            response = view(request, *args, **kwargs)
            # Most views use render(); keep delayed template responses inside the
            # same scope too, rather than leaking the override into other modules.
            if hasattr(response, "render") and not response.is_rendered:
                response.render()
            return response

    return wrapped
