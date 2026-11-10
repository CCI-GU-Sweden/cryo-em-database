from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import SampleOwner
from .services import create_preparation_session
from .storage import change_box, correct_last_box_action, register_box
from .storage_models import BoxEvent, GridBox, GridBoxType, Puck


class StorageTests(TestCase):
    def test_puck_detail_lists_only_its_boxes_and_requires_staff(self):
        box = self.create("Box in selected puck", self.puck)
        self.create("Box in stock")
        self.client.force_login(self.actor)
        url = reverse("registry:puck_detail", args=[self.puck.pk])
        response = self.client.get(url)
        self.assertContains(response, box.name)
        self.assertNotContains(response, "Box in stock")
        self.assertContains(response, "1/12")
        self.assertContains(response, "0/8")
        self.assertContains(response, reverse("registry:box_detail", args=[box.pk]))
        self.assertContains(self.client.get(reverse("registry:puck_inventory")), url)
        self.actor.is_cci_staff = False
        self.actor.save()
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_password_confirmed_puck_registration(self):
        from .storage import register_puck

        self.actor.set_password("test-puck-password")
        self.actor.save()
        with self.assertRaises(ValidationError):
            register_puck(actor=self.actor, name="Orange", password="incorrect")
        puck = register_puck(actor=self.actor, name=" Orange ", password="test-puck-password")
        self.assertEqual(puck.color, "orange")
        self.assertFalse(puck.in_dewar)
        with self.assertRaises(ValidationError):
            register_puck(actor=self.actor, name="ORANGE", password="test-puck-password")
        self.client.force_login(self.actor)
        url = reverse("registry:puck_inventory")
        self.assertContains(self.client.get(url), "0/12")
        self.assertEqual(
            self.client.post(url, {"name": "Pink", "password": "test-puck-password"}).status_code,
            302,
        )
        self.actor.is_cci_staff = False
        self.actor.save()
        with self.assertRaises(PermissionDenied):
            register_puck(actor=self.actor, name="Denied", password="test-puck-password")
        self.assertEqual(self.client.get(url).status_code, 403)

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

    def test_password_correction_preserves_transfer_history(self):
        self.actor.set_password("test-correction-password")
        self.actor.save()
        box = self.create(puck=self.puck)
        box = change_box(
            actor=self.actor,
            box_id=box.pk,
            expected_version=box.version,
            action="transfer",
            transfer_destination="Partner lab",
        )
        event = box.events.first()
        args = dict(
            actor=self.actor,
            box_id=box.pk,
            expected_version=box.version,
            event_id=event.pk,
            reason="Entered by mistake",
        )
        with self.assertRaises(ValidationError):
            correct_last_box_action(**args, password="incorrect")
        box = correct_last_box_action(**args, password="test-correction-password")
        self.assertIsNone(box.transferred_at)
        self.assertEqual(box.puck_id, self.puck.pk)
        event.refresh_from_db()
        self.assertEqual(event.destination, "Partner lab")
        self.assertEqual(box.events.first().correction_of_id, event.pk)
        with self.assertRaises(ValidationError):
            correct_last_box_action(**args, password="test-correction-password")

    def test_correction_rejects_full_previous_puck(self):
        self.actor.set_password("test-correction-password")
        self.actor.save()
        box = self.change(self.create(puck=self.puck))
        event = box.events.first()
        for n in range(12):
            self.create(f"Capacity {n}", self.puck)
        with self.assertRaisesMessage(ValidationError, "12 gridboxes"):
            correct_last_box_action(
                actor=self.actor,
                box_id=box.pk,
                expected_version=box.version,
                event_id=event.pk,
                password="test-correction-password",
                reason="Mistake",
            )
        box.refresh_from_db()
        self.assertIsNone(box.puck_id)
        self.assertEqual(box.events.count(), 2)

    def test_correction_form_uses_password_without_username(self):
        self.actor.set_password("test-correction-password")
        self.actor.save()
        box = self.change(self.create(), "discard")
        event = box.events.first()
        self.client.force_login(self.actor)
        url = reverse("registry:box_detail", args=[box.pk])
        response = self.client.get(url)
        self.assertContains(response, "Correct last action")
        self.assertNotContains(response, 'name="username"')
        payload = {
            "intent": "correct",
            "expected_version": box.version,
            "event_id": event.pk,
            "password": "test-correction-password",
            "reason": "Accidental discard",
        }
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.actor)
        self.assertEqual(csrf_client.post(url, payload).status_code, 403)
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        box.refresh_from_db()
        self.assertFalse(box.discarded)


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

    def test_two_grids_cannot_claim_the_same_slot(self):
        from concurrent.futures import ThreadPoolExecutor

        from django.db import close_old_connections

        from .grid_storage import place_grid
        from .storage_models import Cane, Dewar

        actor = get_user_model().objects.create_user(username="slot-race", is_cci_staff=True)
        dewar, _ = Dewar.objects.get_or_create(name="Dewar 1")
        cane, _ = Cane.objects.get_or_create(dewar=dewar, name="Cane 1")
        puck, _ = Puck.objects.get_or_create(cane=cane, color="green")
        kind, _ = GridBoxType.objects.get_or_create(
            code="race-slot",
            defaults={
                "name": "Race layout",
                "svg": "grid-boxes/unclip-4.svg",
                "layout": {"unclipped": {"capacity": 4, "clipped": False}},
            },
        )
        box = register_box(actor=actor, name="Race box", box_type_id=kind.pk, puck_id=puck.pk)
        owner = SampleOwner.objects.create(name="Slot race owner", code="race")
        grids = list(
            create_preparation_session(
                actor=actor,
                owner=owner,
                prepared_at=timezone.now(),
                grid_count=2,
                preparation={},
                request_token=uuid4(),
            ).grids.all()
        )
        slot = box.slots.first()

        def attempt(grid):
            close_old_connections()
            try:
                place_grid(
                    actor=actor,
                    grid_id=grid.pk,
                    slot_id=slot.pk,
                    clipped=False,
                    expected_version=grid.version,
                    occurred_at=timezone.now(),
                )
                return True
            except ValidationError:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(attempt, grids))
        self.assertEqual(sum(results), 1)
        self.assertEqual(sum(g.physical_events.count() for g in grids), 1)
