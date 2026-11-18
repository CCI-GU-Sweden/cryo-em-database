"""Registry administration shared by dashboard and standalone installations."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import AdminOwnerForm
from .models import OwnerAccessGrant, SampleOwner
from .permissions import current_staff
from .services import save_administration_record


def current_administrator(actor):
    actor = current_staff(actor)
    if actor.role != "admin":
        raise PermissionDenied("Only a facility administrator can manage owners and grants.")
    return actor


class OwnerGrantForm(forms.ModelForm):
    class Meta:
        model = OwnerAccessGrant
        fields = ["user", "role"]


def save_form(form, actor):
    """Preserve service validation and auditing for both management forms."""
    if not form.is_valid():
        return False
    try:
        save_administration_record(actor=actor, instance=form.save(commit=False))
    except ValidationError as error:
        for message in error.messages:
            form.add_error(None, message)
        return False
    return True


@login_required
@require_http_methods(["GET", "POST"])
def owner_edit(request, pk):
    actor = current_administrator(request.user)
    owner = get_object_or_404(SampleOwner, pk=pk)
    form = AdminOwnerForm(request.POST if request.method == "POST" else None, instance=owner)
    if request.method == "POST" and save_form(form, actor):
        messages.success(request, "Sample owner updated.")
        return redirect("registry:owner_list")
    return render(request, "registry/owner_edit.html", {"owner": owner, "form": form})


@login_required
@require_http_methods(["GET", "POST"])
def owner_grants(request, pk):
    actor = current_administrator(request.user)
    owner = get_object_or_404(SampleOwner, pk=pk)
    form = OwnerGrantForm(
        request.POST if request.method == "POST" else None,
        instance=OwnerAccessGrant(owner=owner),
    )
    if request.method == "POST" and save_form(form, actor):
        messages.success(request, "Owner access grant registered.")
        return redirect("registry:owner_grants", pk=owner.pk)
    return render(
        request,
        "registry/owner_grants.html",
        {"owner": owner, "grants": owner.grants.select_related("user"), "form": form},
    )


@login_required
@require_http_methods(["GET", "POST"])
def owner_grant_edit(request, pk):
    actor = current_administrator(request.user)
    grant = get_object_or_404(OwnerAccessGrant.objects.select_related("owner"), pk=pk)
    form = OwnerGrantForm(request.POST if request.method == "POST" else None, instance=grant)
    if request.method == "POST" and save_form(form, actor):
        messages.success(request, "Owner access grant updated.")
        return redirect("registry:owner_grants", pk=grant.owner_id)
    return render(request, "registry/owner_grant_edit.html", {"grant": grant, "form": form})
