"""Authorization rules used by HTTP views and direct service calls alike."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from .models import DeletedGrid, Grid, SampleOwner


def current_staff(actor):
    # Reload privileges so stale user objects cannot retain a revoked account.
    user = get_user_model().objects.filter(pk=getattr(actor, "pk", None), is_active=True).first()
    if user is None or user.role not in ("staff", "admin"):
        raise PermissionDenied("You need an active CCI staff account.")
    return user


def visible_grids(actor):
    """The shared row-access boundary for registry browsing and Excel export.

    Registry access currently belongs to CCI staff and facility administrators.
    Future read-only access must be added here, rather than only in the UI.
    """
    current_staff(actor)
    return Grid.objects.active()


def require_grid_importer(actor):
    """Import is a write capability available to active Staff and Admin users."""
    return current_staff(actor)


def visible_owners(actor):
    """Owner visibility is facility-wide, independent of editing grants."""
    current_staff(actor)
    return SampleOwner.objects.all()


def require_session_registration(actor, owner):
    actor = current_staff(actor)
    if not SampleOwner.objects.filter(pk=owner.pk, active=True).exists():
        raise PermissionDenied("Choose an active sample owner for a new preparation session.")
    return actor


def can_edit_grid(actor, grid):
    current_staff(actor)
    return _can_edit_grid(grid)


def _can_edit_grid(grid):
    """All current staff share editing access; archived records stay read-only."""
    return not DeletedGrid.objects.filter(grid_id=grid.pk).exists()


def require_grid_editor(actor, grid):
    actor = current_staff(actor)
    if not _can_edit_grid(grid):
        raise PermissionDenied("Archived grid records are read-only.")
    return actor
