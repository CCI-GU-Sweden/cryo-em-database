"""Preparation records. Physical storage and handling will be a later slice."""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class SampleOwner(models.Model):
    name = models.CharField(max_length=200)
    # Assigned by the owner-registration service; it stays stable after a rename.
    code = models.CharField(
        max_length=40,
        blank=True,
        editable=False,
        help_text="Assigned automatically: four lowercase letters/digits based on the owner name.",
    )
    affiliation = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [models.UniqueConstraint(Lower("code"), name="owner_code_case_unique")]

    def clean(self):
        self.code = self.code.strip()

    def __str__(self):
        return f"{self.name} ({self.code})"


class OwnerAccessGrant(models.Model):
    class Role(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        OPERATOR = "operator", "Operator"
        EDITOR = "editor", "Editor"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    owner = models.ForeignKey(SampleOwner, on_delete=models.PROTECT, related_name="grants")
    role = models.CharField(max_length=20, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "owner"], name="one_owner_grant")]

    def __str__(self):
        return f"{self.user} · {self.owner} · {self.get_role_display()}"


class PreparationSession(models.Model):
    owner = models.ForeignKey(SampleOwner, on_delete=models.PROTECT)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    prepared_at = models.DateTimeField(null=True)
    experiment_reference = models.CharField(max_length=200, blank=True)
    project_reference = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    defaults_schema_version = models.PositiveIntegerField(default=4)
    defaults = models.JSONField(default=dict)
    # Used to identify a repeated form submission; never an identifier for a grid.
    request_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session {self.pk} · {self.owner}"


class Grid(models.Model):
    grid_number = models.CharField(max_length=80, unique=True)
    session = models.ForeignKey(PreparationSession, on_delete=models.PROTECT, related_name="grids")
    copied_from_grid = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True)
    sample_description = models.TextField(blank=True)
    sample_concentration_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    sample_concentration_unit = models.CharField(max_length=40, blank=True)
    buffer_description = models.TextField(blank=True)
    grid_type = models.CharField(max_length=200, blank=True)
    grid_box_number = models.CharField(max_length=100, blank=True)
    grid_type_reference = models.CharField(max_length=200, blank=True)
    carbon_description = models.CharField(max_length=200, blank=True)
    carbon_thickness_nm = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    glow_atmosphere = models.CharField(max_length=100, blank=True)
    glow_polarity = models.CharField(max_length=100, blank=True)
    glow_current_ma = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    glow_duration_s = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    sample_volume_ul = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    temperature_c = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    humidity_percent = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    blot_time_s = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    hold_time_s = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    # Blot force is an instrument scale; do not invent units or forbid negatives yet.
    blot_force = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    multiple_blot = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(Lower("grid_number"), name="grid_number_case_unique"),
            *[
                models.CheckConstraint(
                    condition=models.Q(**{f"{field}__gte": 0}), name=f"{field}_nonnegative"
                )
                for field in (
                    "sample_concentration_value",
                    "carbon_thickness_nm",
                    "glow_duration_s",
                    "sample_volume_ul",
                    "blot_time_s",
                    "hold_time_s",
                )
            ],
            models.CheckConstraint(
                condition=models.Q(multiple_blot__gte=0),
                name="multiple_blot_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(humidity_percent__gte=0, humidity_percent__lte=100),
                name="humidity_in_percent_range",
            ),
        ]

    def clean(self):
        from .preparation import normalize_preparation_text

        for name in ("carbon_description", "glow_atmosphere", "glow_polarity"):
            setattr(self, name, normalize_preparation_text(name, getattr(self, name)))

    def __str__(self):
        return self.grid_number


class GridIdentifierCounter(models.Model):
    """One counter per owner; allocation rolls back with a failed batch."""

    namespace = models.CharField(max_length=40, primary_key=True)
    next_number = models.PositiveIntegerField(default=1)


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=80)
    operation = models.CharField(max_length=40)
    changes = models.JSONField(default=dict)
    recorded_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=40, default="ui")

    class Meta:
        ordering = ["-recorded_at", "-pk"]


class PreparationSuggestion(models.Model):
    """Optional private vocabulary seeded from a source workbook, not a grid."""

    field_name = models.CharField(max_length=80)
    value = models.CharField(max_length=500)
    source = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["field_name", "value"], name="unique_preparation_suggestion"
            )
        ]
