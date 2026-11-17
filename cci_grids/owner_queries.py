"""Owner browsing search shared by the HTML directory and Excel export."""

from django.db.models import Q

from .permissions import visible_owners


def search_owners(parameters, *, actor):
    query = parameters.get("q", "").strip()
    owners = visible_owners(actor)
    if query:
        owners = owners.filter(
            Q(name__icontains=query) | Q(code__icontains=query) | Q(affiliation__icontains=query)
        )
    return query, owners
