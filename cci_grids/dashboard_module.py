"""Dashboard contract v1; imported only when the host enables this module."""

from dashboard.modules import DashboardModule
from django.core.exceptions import PermissionDenied

from .models import Grid
from .permissions import current_staff, visible_grids


def can_view(user):
    if not getattr(user, "is_authenticated", False):
        return False
    try:
        current_staff(user)
    except PermissionDenied:
        return False
    return True


def overview_metrics(user):
    # The same boundary protects both direct calls and the dashboard overview.
    grids = visible_grids(user)
    stored = grids.filter(
        status__in=[Grid.Status.IN_STORAGE, Grid.Status.SCREENED_RECOVERED],
        gridslot__box__discarded=False,
        gridslot__box__transferred_at__isnull=True,
    )
    needs_review = grids.filter(gridslot__isnull=True).exclude(
        status__in=[
            Grid.Status.TRANSFERRED,
            Grid.Status.DISCARDED,
            Grid.Status.SCREENED_DISCARDED,
            Grid.Status.DELETED,
        ]
    )
    return [
        {"label": "Grids stored at CCI", "value": str(stored.count())},
        {"label": "Unknown location — needs review", "value": str(needs_review.count())},
    ]


module = DashboardModule(
    key="cci-grids",
    name="Grid Registry",
    eyebrow="Cryo-EM preparation and storage",
    icon="▦",
    url_name="registry:grid_list",
    urlconf="cci_grids.dashboard_urls",
    can_view=can_view,
    get_metrics=overview_metrics,
)
