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


def require_editor(actor, owner):
    actor = current_staff(actor)
    if not editable_owners(actor).filter(pk=owner.pk).exists():
        raise PermissionDenied("You do not have permission to edit this sample owner's records.")
    return actor
