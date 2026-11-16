from io import BytesIO
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .excel import read_workbook
from .grid_storage import correct_grid_outcome, location, place_grid, record_grid_outcome
from .models import Grid, SampleOwner
from .services import create_preparation_session
from .storage import change_box, correct_last_box_action, register_box
from .storage_models import GridBoxType, Puck


class GridStorageTests(TestCase):
    def test_status_correction_form_requires_password_and_reason(self):
        grid = self.place(
            self.session.grids.first(), self.box.slots.filter(side="unclipped").first()
        )
        grid = record_grid_outcome(
            actor=self.actor,
            grid_id=grid.pk,
            outcome=Grid.Status.DISCARDED,
            reason="",
            expected_version=grid.version,
        )
        event = grid.physical_events.order_by("-pk").first()
        self.client.force_login(self.actor)
        url = reverse("registry:grid_detail", args=[grid.pk])
        self.assertContains(self.client.get(url), "Correct last status change")
        data = {
            "intent": "correct_status",
            "expected_version": grid.version,
            "event_id": event.pk,
            "approval": "wrong",
            "reason": "mistake",
        }
        self.assertContains(self.client.post(url, data), "Type approve to confirm")
        grid.refresh_from_db()
        self.assertEqual(grid.status, Grid.Status.DISCARDED)
        response = self.client.post(url, {**data, "approval": "approve"})
        self.assertRedirects(response, url)
        grid.refresh_from_db()
        self.assertEqual(grid.status, Grid.Status.IN_STORAGE)

    def test_correct_discard_requires_password_restores_slot_and_preserves_events(self):
        grid = self.place(
            self.session.grids.first(), self.box.slots.filter(side="unclipped").first()
        )
        slot = grid.gridslot
        grid = record_grid_outcome(
            actor=self.actor,
            grid_id=grid.pk,
            outcome=Grid.Status.SCREENED_DISCARDED,
            reason="lost",
            expected_version=grid.version,
        )
        event = grid.physical_events.order_by("-pk").first()
        kwargs = dict(
            actor=self.actor,
            grid_id=grid.pk,
            expected_version=grid.version,
            event_id=event.pk,
            reason="Mistake",
        )
        with self.assertRaisesMessage(ValidationError, "Type approve to confirm"):
            correct_grid_outcome(**kwargs, approval="wrong")
        corrected = correct_grid_outcome(**kwargs, approval="approve")
        slot.refresh_from_db()
        self.assertEqual(slot.grid_id, grid.pk)
        self.assertEqual(corrected.status, Grid.Status.IN_STORAGE)
        self.assertEqual(grid.physical_events.filter(operation="discarded").count(), 1)
        self.assertEqual(
            grid.physical_events.get(operation="status_correction").details["corrected_event_id"],
            event.pk,
        )
        with self.assertRaises(ValidationError):
            correct_grid_outcome(**kwargs, approval="approve")

    def test_correction_refuses_slot_reused_by_another_grid(self):
        grid, other = self.session.grids.all()
        slot = self.box.slots.filter(side="unclipped").first()
        grid = self.place(grid, slot)
        grid = record_grid_outcome(
            actor=self.actor,
            grid_id=grid.pk,
            outcome=Grid.Status.DISCARDED,
            reason="",
            expected_version=grid.version,
        )
        event = grid.physical_events.order_by("-pk").first()
        self.place(other, slot)
        with self.assertRaisesMessage(ValidationError, "slot is occupied"):
            correct_grid_outcome(
                actor=self.actor,
                grid_id=grid.pk,
                expected_version=grid.version,
                event_id=event.pk,
                approval="approve",
                reason="Mistake",
            )
        grid.refresh_from_db()
        self.assertEqual(grid.status, Grid.Status.DISCARDED)

    def test_screen_recover_then_discard_releases_slot_and_preserves_history(self):
        grid = self.session.grids.first()
        slot = self.box.slots.filter(side="unclipped").first()
        grid = self.place(grid, slot)
        grid = record_grid_outcome(
            actor=self.actor,
            grid_id=grid.pk,
            outcome=Grid.Status.SCREENED_RECOVERED,
            reason="",
            expected_version=grid.version,
        )
        slot.refresh_from_db()
        self.assertEqual(slot.grid_id, grid.pk)
        self.assertEqual(grid.status, Grid.Status.SCREENED_RECOVERED)
        grid = record_grid_outcome(
            actor=self.actor,
            grid_id=grid.pk,
            outcome=Grid.Status.DISCARDED,
            reason="broken",
            expected_version=grid.version,
        )
        slot.refresh_from_db()
        self.assertIsNone(slot.grid_id)
        self.assertEqual(grid.status, Grid.Status.SCREENED_DISCARDED)
        self.assertEqual(grid.physical_events.filter(operation="screened").count(), 1)
        self.assertEqual(
            grid.physical_events.get(operation="discarded").details["reason"], "broken"
        )
        self.assertEqual(location(grid), "Discarded at CCI")
        self.client.force_login(self.actor)
        self.assertNotContains(self.client.get(reverse("registry:grid_list")), grid.grid_number)
        discarded = self.client.get(
            reverse("registry:discarded_grid_list"), {"q": grid.grid_number}
        )
        self.assertContains(discarded, grid.grid_number)
        self.assertContains(discarded, "Discarded at CCI")
        response = self.client.get(reverse("registry:owner_excel_export"), {"q": self.owner.code})
        rows = read_workbook(BytesIO(response.content))["grids"]
        exported = next(row for row in rows if row["grid_number"] == grid.grid_number)
        self.assertEqual(exported["storage_status"], "Discarded at CCI")
        self.assertEqual(exported["grid_status"], "Screened and discarded")
        with self.assertRaises(ValidationError):
            self.place(grid, slot)

    def test_status_controls_require_recorded_slot_for_screening(self):
        grid = self.session.grids.first()
        self.client.force_login(self.actor)
        response = self.client.get(reverse("registry:grid_detail", args=[grid.pk]))
        self.assertContains(response, "Grid status")
        response = self.client.post(
            reverse("registry:grid_detail", args=[grid.pk]),
            {
                "intent": "outcome",
                "outcome": Grid.Status.SCREENED_RECOVERED,
                "expected_version": grid.version,
            },
        )
        self.assertContains(response, "Record the grid&#x27;s box and slot before screening.")
        grid.refresh_from_db()
        self.assertEqual(grid.status, Grid.Status.UNKNOWN)

    def test_separate_preparation_and_storage_filters_combine_and_export(self):
        grid = self.session.grids.first()
        self.place(grid, self.box.slots.filter(side="unclipped").first())
        self.client.force_login(self.actor)
        params = {
            "filters-TOTAL_FORMS": "1",
            "filters-INITIAL_FORMS": "0",
            "filters-0-property": "grid_number",
            "filters-0-contains": grid.grid_number,
            "storage-TOTAL_FORMS": "2",
            "storage-INITIAL_FORMS": "0",
            "storage-0-property": "puck",
            "storage-0-puck": self.box.puck_id,
            "storage-1-property": "box",
            "storage-1-box": self.box.pk,
        }
        response = self.client.get(reverse("registry:grid_list"), params)
        self.assertContains(response, "Sample and preparation filters")
        self.assertContains(response, "Storage filters")
        self.assertEqual(list(response.context["page"].object_list), [grid])
        self.assertEqual(self.client.get(reverse("registry:excel_export"), params).status_code, 200)
        params["storage-1-box"] = "999999"
        response = self.client.get(reverse("registry:grid_list"), params)
        self.assertEqual(response.context["page"].paginator.count, 0)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(self.client.get(reverse("registry:excel_export"), params).status_code, 400)

    def test_storage_slot_and_clipping_filters(self):
        grid = self.session.grids.first()
        slot = self.box.slots.filter(side="clipped").first()
        self.place(grid, slot, True)
        self.client.force_login(self.actor)
        params = {
            "storage-TOTAL_FORMS": "2",
            "storage-INITIAL_FORMS": "0",
            "storage-0-property": "slot",
            "storage-0-slot": slot.pk,
            "storage-1-property": "clipped",
            "storage-1-clipped": "yes",
        }
        response = self.client.get(reverse("registry:grid_list"), params)
        self.assertEqual(response.context["page"].paginator.count, 1)
        params["storage-1-clipped"] = "no"
        self.assertEqual(
            self.client.get(reverse("registry:grid_list"), params).context["page"].paginator.count,
            0,
        )

    def test_registry_storage_links_to_puck_and_box_and_handles_unknown_and_transfer(self):
        from django.utils.html import escape

        a, b = self.session.grids.all()
        self.box.name = "<synthetic box>"
        self.box.save(update_fields=["name"])
        self.place(a, self.box.slots.filter(side="unclipped").first())
        self.client.force_login(self.actor)
        url = reverse("registry:grid_list")
        response = self.client.get(url)
        self.assertContains(response, reverse("registry:puck_detail", args=[self.box.puck_id]))
        self.assertContains(response, reverse("registry:box_detail", args=[self.box.pk]))
        self.assertContains(response, escape(self.box.name), html=False)
        self.assertContains(response, "Unknown — needs review")
        response = self.client.get(reverse("registry:session_detail", args=[self.session.pk]))
        self.assertContains(response, reverse("registry:box_detail", args=[self.box.pk]))
        change_box(
            actor=self.actor,
            box_id=self.box.pk,
            expected_version=self.box.version,
            action="transfer",
            transfer_destination="Partner lab",
        )
        response = self.client.get(url)
        self.assertNotContains(response, a.grid_number)
        response = self.client.get(reverse("registry:transferred_grid_list"), {"q": "Partner lab"})
        self.assertContains(response, a.grid_number)
        self.assertContains(response, "Transferred to Partner lab")
        self.assertContains(response, reverse("registry:box_detail", args=[self.box.pk]))
        self.assertNotContains(response, reverse("registry:puck_detail", args=[self.box.puck_id]))

    def test_loaded_boxes_and_pucks_cannot_be_returned_to_stock(self):
        from .storage import record_puck_location

        grid = self.place(
            self.session.grids.first(), self.box.slots.filter(side="unclipped").first()
        )
        puck = self.box.puck
        puck.refresh_from_db()
        event_count = self.box.events.count()
        with self.assertRaisesMessage(ValidationError, "Empty it before returning it to stock"):
            change_box(
                actor=self.actor,
                box_id=self.box.pk,
                expected_version=self.box.version,
                action="move",
                puck_id=None,
            )
        with self.assertRaisesMessage(ValidationError, "Empty the boxes in this puck"):
            record_puck_location(
                actor=self.actor, puck_id=puck.pk, expected_version=puck.version, in_dewar=False
            )
        self.box.refresh_from_db()
        puck.refresh_from_db()
        self.assertEqual(self.box.puck_id, puck.pk)
        self.assertTrue(puck.in_dewar)
        self.assertEqual(self.box.events.count(), event_count)
        self.assertIn(self.box.name, location(grid))
        self.client.force_login(self.actor)
        response = self.client.post(
            reverse("registry:puck_detail", args=[puck.pk]),
            {
                "in_dewar": "no",
                "expected_version": puck.version,
            },
        )
        self.assertContains(response, "Empty the boxes in this puck")
        response = self.client.post(
            reverse("registry:box_detail", args=[self.box.pk]),
            {
                "action": "move",
                "puck": "",
                "expected_version": self.box.version,
                "occurred_at": timezone.now().isoformat(),
            },
        )
        self.assertContains(response, "Empty it before returning it to stock")

    def test_detail_contains_storage_group_between_clipping_and_notes(self):
        self.client.force_login(self.actor)
        grid = self.session.grids.first()
        response = self.client.get(reverse("registry:grid_detail", args=[grid.pk]))
        html = response.content.decode()
        self.assertLess(
            html.index("<summary>Clipping</summary>"), html.index('id="storage-actions"')
        )
        self.assertLess(
            html.index('id="storage-actions"'), html.index("<summary>Grid notes</summary>")
        )
        self.assertContains(response, 'form="grid-preparation-form"')
        self.assertContains(response, "inline_grid_storage.js")

    def test_inline_storage_selection_placement_and_new_box_stay_in_panel(self):
        self.client.force_login(self.actor)
        grid = self.session.grids.first()
        url = reverse("registry:grid_storage", args=[grid.pk]) + "?inline=1"
        response = self.client.get(url, {"inline": "1", "box": self.box.pk})
        self.assertContains(response, "data-storage-content")
        self.assertNotContains(response, "<html")
        slot = self.box.slots.filter(side="unclipped").first()
        response = self.client.post(
            url,
            {
                "intent": "place",
                "box": self.box.pk,
                "slot": slot.pk,
                "clipped": "0",
                "expected_version": grid.version,
                "occurred_at": timezone.now().isoformat(),
            },
            follow=True,
        )
        self.assertContains(response, 'data-placed="1"')
        grid.refresh_from_db()
        self.assertContains(response, f'data-version="{grid.version}"')
        self.assertIn(self.box.name, location(grid))
        response = self.client.post(
            url,
            {
                "intent": "new_box",
                "name": "Panel box",
                "box_type": self.box.box_type_id,
                "puck": self.box.puck_id,
            },
            follow=True,
        )
        self.assertContains(response, "<h2>Panel box</h2>")
        self.assertNotContains(response, "<html")

    def test_default_placement_time_follows_same_second_clipping_update(self):
        from unittest.mock import patch

        from .grid_storage import save_preparation_and_clipping
        from .grid_storage_views import PlacementForm

        grid = self.session.grids.first()
        instant = timezone.now().replace(microsecond=500000)
        with patch("registry.grid_storage.timezone.now", return_value=instant):
            grid, _ = save_preparation_and_clipping(
                actor=self.actor,
                grid_id=grid.pk,
                preparation={},
                clipped=True,
                expected_version=grid.version,
            )
            field = PlacementForm()["occurred_at"]
            self.assertIn('step="1"', str(field))
            entered = field.field.clean(field.field.widget.format_value(field.value()))
        self.assertGreater(entered, instant)
        place_grid(
            actor=self.actor,
            grid_id=grid.pk,
            slot_id=self.box.slots.filter(side="clipped").first().pk,
            clipped=True,
            expected_version=grid.version,
            occurred_at=entered,
        )

    def test_preparation_clipping_change_releases_incompatible_location(self):
        from .grid_storage import save_preparation_and_clipping

        grid = self.session.grids.first()
        slot = self.box.slots.filter(side="unclipped").first()
        grid = self.place(grid, slot)
        defaults = grid.session.defaults.copy()
        grid, released = save_preparation_and_clipping(
            actor=self.actor,
            grid_id=grid.pk,
            expected_version=grid.version,
            preparation={"notes": "Updated"},
            clipped=True,
        )
        self.assertTrue(released)
        self.assertTrue(grid.is_clipped)
        slot.refresh_from_db()
        self.assertIsNone(slot.grid_id)
        self.assertIn("needs review", location(grid))
        self.assertEqual(grid.session.defaults, defaults)
        grid, released = save_preparation_and_clipping(
            actor=self.actor,
            grid_id=grid.pk,
            expected_version=grid.version,
            preparation={},
            clipped=False,
        )
        self.assertFalse(grid.is_clipped)
        self.assertFalse(released)
        self.assertEqual(grid.physical_events.filter(operation="clipping_updated").count(), 2)

    def test_preparation_view_exposes_and_saves_clipping(self):
        from .preparation import preparation_snapshot

        grid = self.session.grids.first()
        self.client.force_login(self.actor)
        url = reverse("registry:grid_detail", args=[grid.pk])
        self.assertContains(self.client.get(url), 'name="is_clipped"')
        data = {
            key: value if value is not None else ""
            for key, value in preparation_snapshot(grid).items()
        }
        data.update(expected_version=grid.version, is_clipped="on")
        self.assertEqual(self.client.post(url, data).status_code, 302)
        grid.refresh_from_db()
        self.assertTrue(grid.is_clipped)

    def test_stock_box_requires_space_and_failed_placement_changes_nothing(self):
        stock = register_box(actor=self.actor, name="Needs puck", box_type_id=self.box.box_type_id)
        for n in range(11):
            register_box(
                actor=self.actor,
                name=f"Full puck {n}",
                box_type_id=self.box.box_type_id,
                puck_id=self.box.puck_id,
            )
        grid = self.session.grids.first()
        slot = stock.slots.filter(side="unclipped").first()
        self.client.force_login(self.actor)
        response = self.client.get(
            reverse("registry:grid_storage", args=[grid.pk]), {"box_name": stock.name}
        )
        self.assertFalse(
            response.context["form"].fields["puck"].queryset.filter(pk=self.box.puck_id).exists()
        )
        with self.assertRaisesMessage(ValidationError, "12 gridboxes"):
            place_grid(
                actor=self.actor,
                grid_id=grid.pk,
                slot_id=slot.pk,
                clipped=False,
                expected_version=grid.version,
                occurred_at=timezone.now(),
                puck_id=self.box.puck_id,
            )
        stock.refresh_from_db()
        slot.refresh_from_db()
        self.assertIsNone(stock.puck_id)
        self.assertIsNone(slot.grid_id)
        self.assertEqual(stock.events.count(), 1)

    def test_incompatible_box_selection_explains_why_slots_are_unavailable(self):
        box = register_box(
            actor=self.actor,
            name="Unclipped only",
            box_type_id=GridBoxType.objects.get(code="unclipped4").pk,
        )
        self.client.force_login(self.actor)
        url = reverse("registry:grid_storage", args=[self.session.grids.first().pk])
        response = self.client.get(url, {"box_name": box.name, "clipped": "1"})
        self.assertContains(response, "cannot accept a clipped grid")
        self.assertIsNone(response.context["box"])
        response = self.client.get(url, {"box_name": box.name})
        self.assertContains(response, "Available slot")
        self.assertEqual(response.context["form"].fields["slot"].queryset.count(), 4)

    def test_box_picker_includes_free_stock_and_filters_by_exact_selection(self):
        stock = register_box(actor=self.actor, name="Stock box", box_type_id=self.box.box_type_id)
        self.client.force_login(self.actor)
        grid = self.session.grids.first()
        url = reverse("registry:grid_storage", args=[grid.pk])
        response = self.client.get(url)
        self.assertContains(response, 'value="Stock box"')
        self.assertContains(response, 'list="available-boxes"')
        response = self.client.get(url, {"box_name": "Stock box"})
        self.assertEqual(response.context["box"], stock)
        self.assertContains(response, "Place this box in puck")
        slot = stock.slots.filter(side="unclipped").first()
        with self.assertRaisesMessage(ValidationError, "Choose the puck"):
            self.place(grid, slot)
        grid = place_grid(
            actor=self.actor,
            grid_id=grid.pk,
            slot_id=slot.pk,
            clipped=False,
            expected_version=grid.version,
            occurred_at=timezone.now(),
            puck_id=self.box.puck_id,
        )
        stock.refresh_from_db()
        self.assertEqual(stock.puck_id, self.box.puck_id)
        self.assertNotIn("Box in stock", location(grid))

    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(
            username="placer", role="staff", password="test-storage"
        )
        cls.owner = SampleOwner.objects.create(name="Storage owner", code="stow")
        cls.session = create_preparation_session(
            actor=cls.actor,
            owner=cls.owner,
            prepared_at=timezone.now(),
            grid_count=2,
            preparation={},
            request_token=uuid4(),
        )
        cls.box = register_box(
            actor=cls.actor,
            name="Mixed storage box",
            box_type_id=GridBoxType.objects.get(code="mixed8").pk,
            puck_id=Puck.objects.first().pk,
        )

    def place(self, grid, slot, clipped=False):
        return place_grid(
            actor=self.actor,
            grid_id=grid.pk,
            slot_id=slot.pk,
            clipped=clipped,
            expected_version=grid.version,
            occurred_at=timezone.now(),
        )

    def test_placement_clipping_movement_and_transfer_correction(self):
        a, b = self.session.grids.all()
        u = self.box.slots.filter(side="unclipped").first()
        c = self.box.slots.filter(side="clipped").first()
        a = self.place(a, u)
        puck = self.box.puck
        puck.refresh_from_db()
        self.assertTrue(puck.in_dewar)
        self.client.force_login(self.actor)
        puck_page = self.client.get(reverse("registry:puck_inventory"))
        self.assertContains(puck_page, "In dewar")
        self.assertContains(puck_page, "1/12")
        inventory = self.client.get(reverse("registry:inventory"))
        self.assertContains(inventory, "Occupied slots")
        self.assertContains(inventory, "1/8")
        with self.assertRaises(ValidationError):
            self.place(b, u)
        a = self.place(a, c, True)
        u.refresh_from_db()
        self.assertIsNone(u.grid_id)
        self.assertTrue(a.is_clipped)
        self.assertEqual(a.physical_events.count(), 3)
        box = change_box(
            actor=self.actor,
            box_id=self.box.pk,
            expected_version=self.box.version,
            action="transfer",
            transfer_destination="Other lab",
        )
        self.assertIn("Other lab", location(a))
        a.refresh_from_db()
        with self.assertRaises(ValidationError):
            self.place(a, c, True)
        correct_last_box_action(
            actor=self.actor,
            box_id=box.pk,
            expected_version=box.version,
            event_id=box.events.first().pk,
            approval="approve",
            reason="Mistake",
        )
        self.assertNotIn("Transferred", location(a))
        a.refresh_from_db()
        self.assertEqual(a.status, Grid.Status.IN_STORAGE)
        self.assertNotContains(
            self.client.get(reverse("registry:transferred_grid_list")), a.grid_number
        )
        self.assertContains(self.client.get(reverse("registry:grid_list")), a.grid_number)
        self.assertEqual(a.physical_events.count(), 5)

    def test_ui_keeps_session_context_and_inline_registration(self):
        self.client.force_login(self.actor)
        grid = self.session.grids.first()
        url = reverse("registry:grid_storage", args=[grid.pk])
        response = self.client.get(url, {"box": self.box.pk, "clipped": "1"})
        self.assertContains(response, "C1")
        self.assertNotContains(response, ">U1<")
        self.assertContains(response, "Register new gridbox")
        response = self.client.post(
            url,
            {
                "intent": "new_box",
                "clipped": "1",
                "name": "Inline box",
                "box_type": self.box.box_type_id,
                "puck": self.box.puck_id,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("box=", response.url)
        self.assertContains(
            self.client.get(reverse("registry:session_detail", args=[self.session.pk])),
            "Grid locations and actions",
        )
