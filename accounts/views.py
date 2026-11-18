from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render


@login_required
def home(request):
    """Only active CCI members and facility administrators see the local registry."""
    if not request.user.is_active or request.user.role not in ("staff", "admin"):
        raise PermissionDenied("Ask a CCI administrator to enable your registry access.")
    return render(request, "home.html")
