"""Authorization rules used by HTTP views and direct service calls alike."""

from django.core.exceptions import PermissionDenied

from accounts.models import User

from .models import OwnerAccessGrant, SampleOwner


def current_staff(actor):
    # Reload privileges so stale user objects cannot retain a revoked account.
    user = User.objects.filter(pk=getattr(actor, "pk", None), is_active=True).first()
    if user is None or not (user.is_superuser or user.is_cci_staff):
        raise PermissionDenied("You need an active CCI staff account.")
    return user


def editable_owners(actor):
    actor = current_staff(actor)
    owners = SampleOwner.objects.filter(active=True)
    if actor.is_superuser:
        return owners
    return owners.filter(grants__user=actor, grants__role=OwnerAccessGrant.Role.EDITOR)


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
    actor = current_staff(actor)
    if not SampleOwner.objects.filter(pk=grid.session.owner_id, active=True).exists():
        return False
    return (
        actor.is_superuser
        or grid.session.prepared_by_id == actor.pk
        or editable_owners(actor).filter(pk=grid.session.owner_id).exists()
    )


def require_grid_editor(actor, grid):
    actor = current_staff(actor)
    if not can_edit_grid(actor, grid):
        raise PermissionDenied(
            "Only the preparation operator, an owner Editor or an administrator can edit this grid."
        )
    return actor
