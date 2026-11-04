"""Authorization rules used by HTTP views and direct service calls alike."""

from django.core.exceptions import PermissionDenied

from accounts.models import User

from .models import DeletedGrid, SampleOwner


def current_staff(actor):
    # Reload privileges so stale user objects cannot retain a revoked account.
    user = User.objects.filter(pk=getattr(actor, "pk", None), is_active=True).first()
    if user is None or not (user.is_superuser or user.is_cci_staff):
        raise PermissionDenied("You need an active CCI staff account.")
    return user


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
