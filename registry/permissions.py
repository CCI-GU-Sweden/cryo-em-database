"""Authorization rules used by HTTP views and direct service calls alike."""

from django.core.exceptions import PermissionDenied

from accounts.models import User

from .models import DeletedGrid, OwnerAccessGrant, SampleOwner


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
    return _can_edit_grid(current_staff(actor), grid)


def _can_edit_grid(actor, grid):
    """Shared edit rule; public entry points reload staff privileges first."""
    if DeletedGrid.objects.filter(grid_id=grid.pk).exists():
        return False
    if not SampleOwner.objects.filter(pk=grid.session.owner_id, active=True).exists():
        return False
    return (
        actor.is_superuser
        or grid.session.prepared_by_id == actor.pk
        or OwnerAccessGrant.objects.filter(
            user=actor, owner_id=grid.session.owner_id, role=OwnerAccessGrant.Role.EDITOR
        ).exists()
    )


def require_grid_editor(actor, grid):
    actor = current_staff(actor)
    if not _can_edit_grid(actor, grid):
        raise PermissionDenied(
            "Only the preparation operator, an owner Editor or an administrator can edit this grid."
        )
    return actor
