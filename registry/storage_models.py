"""Physical inventory, independent of preparation sessions and projects."""

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class Dewar(models.Model):
    name = models.CharField(max_length=100, unique=True)


class Cane(models.Model):
    dewar = models.ForeignKey(Dewar, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["dewar", "name"], name="unique_cane_name")]


class Puck(models.Model):
    in_dewar = models.BooleanField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    cane = models.ForeignKey(Cane, on_delete=models.PROTECT)
    color = models.CharField(max_length=40)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("color"), "cane", name="unique_puck_color")]

    def __str__(self):
        return self.color.replace("_", " ").title()


class PuckEvent(models.Model):
    puck = models.ForeignKey(Puck, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    in_dewar = models.BooleanField(null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)


class GridBoxType(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    svg = models.CharField(max_length=200)
    # Keys are physical sides; values give their capacities and clipping state.
    layout = models.JSONField()

    def __str__(self):
        return self.name


class GridBox(models.Model):
    name = models.CharField(max_length=100)
    box_type = models.ForeignKey(GridBoxType, on_delete=models.PROTECT)
    puck = models.ForeignKey(Puck, null=True, blank=True, on_delete=models.PROTECT)
    discarded = models.BooleanField(default=False)
    transferred_at = models.DateTimeField(null=True, blank=True)
    transfer_destination = models.CharField(max_length=200, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("name"), name="unique_gridbox_name"),
            models.CheckConstraint(
                condition=models.Q(transferred_at=None) | models.Q(puck=None, discarded=False),
                name="transferred_box_outside_cci",
            ),
            models.CheckConstraint(
                condition=models.Q(discarded=False) | models.Q(puck=None),
                name="discarded_box_has_no_puck",
            ),
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name


class GridSlot(models.Model):
    box = models.ForeignKey(GridBox, related_name="slots", on_delete=models.PROTECT)
    side = models.CharField(max_length=20)
    position = models.PositiveIntegerField()
    grid = models.OneToOneField("registry.Grid", null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["box", "side", "position"], name="unique_box_slot")
        ]
        ordering = ["side", "position"]


class BoxEvent(models.Model):
    correction_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="correction"
    )
    reason = models.TextField(blank=True)
    box = models.ForeignKey(GridBox, related_name="events", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.CharField(max_length=30)
    from_puck = models.ForeignKey(Puck, null=True, on_delete=models.PROTECT, related_name="+")
    to_puck = models.ForeignKey(Puck, null=True, on_delete=models.PROTECT, related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    destination = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-pk"]


class GridEvent(models.Model):
    grid = models.ForeignKey(
        "registry.Grid", related_name="physical_events", on_delete=models.PROTECT
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.CharField(max_length=30)
    occurred_at = models.DateTimeField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    from_slot = models.ForeignKey(GridSlot, null=True, on_delete=models.PROTECT, related_name="+")
    to_slot = models.ForeignKey(GridSlot, null=True, on_delete=models.PROTECT, related_name="+")
    box_event = models.ForeignKey(BoxEvent, null=True, on_delete=models.PROTECT)
    details = models.JSONField(default=dict)
