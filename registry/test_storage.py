from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import SampleOwner
from .services import create_preparation_session
from .storage import change_box, register_box
from .storage_models import BoxEvent, GridBox, GridBoxType, Puck


class StorageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(username="inventory", is_cci_staff=True)
        cls.kind = GridBoxType.objects.get(code="mixed8")
        cls.puck = Puck.objects.first()

    def create(self, name="Box A", puck=None):
        return register_box(
            actor=self.actor, name=name, box_type_id=self.kind.pk, puck_id=getattr(puck, "pk", None)
        )

    def change(self, box, action="move", puck=None):
        return change_box(
            actor=self.actor,
            box_id=box.pk,
            expected_version=box.version,
            action=action,
            puck_id=getattr(puck, "pk", None),
        )

    def test_layouts_and_names(self):
        box = self.create(" Box A ")
        self.assertEqual(box.name, "Box A")
        self.assertEqual(box.slots.count(), 8)
        self.assertEqual(box.slots.filter(side="unclipped").count(), 4)
        with self.assertRaises(ValidationError):
            self.create("box a")
        self.assertEqual(GridBox.objects.count(), 1)

    def test_capacity_and_stock_and_discard_history(self):
        for n in range(12):
            self.create(f"Box {n}", self.puck)
        with self.assertRaises(ValidationError):
            self.create("Overflow", self.puck)
        box = GridBox.objects.first()
        box = self.change(box)
        self.assertIsNone(box.puck_id)
        replacement = self.create("Replacement", self.puck)
        replacement = self.change(replacement, "discard")
        self.assertTrue(replacement.discarded)
        self.assertEqual(replacement.events.count(), 2)
        with self.assertRaises(ValidationError):
            self.change(replacement)
        with self.assertRaises(DatabaseError), transaction.atomic():
            BoxEvent.objects.filter(box=box).update(operation="changed")

    def test_occupied_box_cannot_be_discarded(self):
        owner = SampleOwner.objects.create(name="Inventory test", code="invt")
        grid = create_preparation_session(
            actor=self.actor,
            owner=owner,
            prepared_at=timezone.now(),
            grid_count=1,
            preparation={},
            request_token=uuid4(),
        ).grids.get()
        box = self.create()
        slot = box.slots.first()
        slot.grid = grid
        slot.save()
        with self.assertRaisesMessage(ValidationError, "Remove all grids"):
            self.change(box, "discard")
        with self.assertRaises(DatabaseError), transaction.atomic():
            GridBox.objects.filter(pk=box.pk).update(discarded=True)
        box.refresh_from_db()
        self.assertFalse(box.discarded)
        self.assertEqual(box.events.count(), 1)
        slot.grid = None
        slot.save()
        self.assertTrue(self.change(box, "discard").discarded)

    def test_permissions_and_stale_actions(self):
        box = self.create()
        self.change(box, puck=self.puck)
        with self.assertRaises(ValidationError):
            self.change(box, "discard")
        self.actor.is_cci_staff = False
        self.actor.save()
        with self.assertRaises(PermissionDenied):
            self.create("Denied")
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(reverse("registry:inventory")).status_code, 403)

    def test_inventory_forms_and_detail(self):
        self.client.force_login(self.actor)
        response = self.client.post(
            reverse("registry:inventory"),
            {"name": "UI box", "box_type": self.kind.pk, "puck": self.puck.pk},
        )
        self.assertEqual(response.status_code, 302)
        box = GridBox.objects.get(name="UI box")
        response = self.client.get(reverse("registry:box_detail", args=[box.pk]))
        self.assertContains(response, "clip-unclip-4-4.svg")
        self.assertContains(response, "Empty", count=8)
        self.assertContains(
            self.client.get(reverse("registry:inventory"), {"state": "puck"}), "UI box"
        )

    def test_cci_inventory_excludes_discarded_and_all_includes_them(self):
        active = self.create("Active box")
        discarded = self.change(self.create("Discarded box"), "discard")
        self.client.force_login(self.actor)
        url = reverse("registry:inventory")
        for params in ({}, {"state": "invalid"}):
            response = self.client.get(url, params)
            self.assertEqual(list(response.context["boxes"]), [active])
        self.assertEqual(
            list(self.client.get(url, {"state": "discarded"}).context["boxes"]), [discarded]
        )
        self.assertEqual(self.client.get(url, {"state": "all"}).context["boxes"].count(), 2)

    def test_transfer_requires_destination_and_preserves_history(self):
        box = self.create(puck=self.puck)
        with self.assertRaises(ValidationError):
            self.change(box, "transfer")
        when = timezone.now()
        box = change_box(
            actor=self.actor,
            box_id=box.pk,
            expected_version=box.version,
            action="transfer",
            transfer_destination="Partner laboratory",
            occurred_at=when,
        )
        self.assertIsNone(box.puck_id)
        self.assertEqual(box.transferred_at, when)
        event = box.events.first()
        self.assertEqual(event.from_puck_id, self.puck.pk)
        self.assertEqual(event.destination, "Partner laboratory")
        self.client.force_login(self.actor)
        self.assertNotContains(self.client.get(reverse("registry:inventory")), box.name)
        self.assertContains(
            self.client.get(reverse("registry:inventory"), {"state": "transferred"}), box.name
        )
        self.assertContains(
            self.client.get(reverse("registry:inventory"), {"state": "all"}), box.name
        )
        with self.assertRaises(ValidationError):
            self.change(box)


class InventoryConcurrencyTests(TransactionTestCase):
    def test_concurrent_registration_cannot_overfill_a_puck(self):
        from concurrent.futures import ThreadPoolExecutor

        from django.db import close_old_connections

        from .storage_models import Cane, Dewar

        actor = get_user_model().objects.create_user(username="capacity", is_cci_staff=True)
        dewar, _ = Dewar.objects.get_or_create(name="Dewar 1")
        cane, _ = Cane.objects.get_or_create(dewar=dewar, name="Cane 1")
        puck, _ = Puck.objects.get_or_create(cane=cane, color="black")
        kind, _ = GridBoxType.objects.get_or_create(
            code="concurrency",
            defaults={
                "name": "Test box",
                "svg": "grid-boxes/unclip-4.svg",
                "layout": {"unclipped": {"capacity": 4, "clipped": False}},
            },
        )
        for n in range(11):
            register_box(actor=actor, name=f"Existing {n}", box_type_id=kind.pk, puck_id=puck.pk)

        def attempt(n):
            close_old_connections()
            try:
                register_box(
                    actor=actor, name=f"Concurrent {n}", box_type_id=kind.pk, puck_id=puck.pk
                )
                return True
            except ValidationError:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as workers:
            result = list(workers.map(attempt, [1, 2]))
        self.assertEqual(sum(result), 1)
        self.assertEqual(GridBox.objects.filter(puck=puck).count(), 12)
