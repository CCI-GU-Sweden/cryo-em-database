"""Session browsing filters shared by the HTML list and its Excel export."""

from django.db.models import Count, Q, Value
from django.db.models.functions import Concat

from .forms import SessionBrowseForm
from .models import PreparationSession


def search_sessions(parameters, *, actor):
    form = SessionBrowseForm(parameters, actor=actor)
    sessions = PreparationSession.objects.select_related("owner", "prepared_by").annotate(
        grid_count=Count("grids", filter=Q(grids__deletion__isnull=True)),
        deleted_count=Count("grids", filter=Q(grids__deletion__isnull=False)),
        operator_name=Concat("prepared_by__first_name", Value(" "), "prepared_by__last_name"),
    )
    if not form.is_valid():
        return form, sessions.none()

    data = form.cleaned_data
    query = data["q"]
    if query:
        matches = (
            Q(owner__name__icontains=query)
            | Q(owner__code__icontains=query)
            | Q(prepared_by__username__icontains=query)
            | Q(operator_name__icontains=query)
            | Q(experiment_reference__icontains=query)
            | Q(project_reference__icontains=query)
        )
        number = query.lower().removeprefix("session ").strip()
        if number.isascii() and number.isdigit() and len(number) <= 18:
            matches |= Q(pk=int(number))
        sessions = sessions.filter(matches)
    if data["owner"]:
        sessions = sessions.filter(owner=data["owner"])
    if data["from_date"]:
        sessions = sessions.filter(prepared_at__date__gte=data["from_date"])
    if data["to_date"]:
        sessions = sessions.filter(prepared_at__date__lte=data["to_date"])
    return form, sessions
