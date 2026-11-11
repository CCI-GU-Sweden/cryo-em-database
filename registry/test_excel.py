"""Excel transfers preserve scientific values and never overwrite existing records."""

import copy
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from .excel import GRID_GROUPS, GROUP_COLORS, export_workbook, read_workbook
from .excel_import import import_workbook, preview_import
from .grid_storage import place_grid
from .models import AuditEvent, DeletedGrid, Grid, PreparationSession, SampleOwner
from .services import create_preparation_session, update_grid_preparation
from .storage import change_box, register_box
from .storage_models import Cane, Dewar, GridBoxType, Puck

User = get_user_model()


class ExcelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="excel-admin", is_cci_staff=True)
        cls.staff = User.objects.create_user(username="excel-operator", is_cci_staff=True)
        cls.outsider = User.objects.create_user(username="excel-outsider", is_staff=True)
        cls.owner = SampleOwner.objects.create(name="Synthetic Excel Owner", code="exow")
        cls.session = create_preparation_session(
            actor=cls.staff,
            owner=cls.owner,
            prepared_at=timezone.now(),
            grid_count=2,
            preparation={
                "sample_description": "Synthetic protein",
                "sample_volume_ul": "3.50",
                "hold_time_s": "0",
                "drain_time_s": "1.25",
                "carbon_description": "graphene",
                "carbon_thickness_layers": "2",
                "glow_device": "Quorum – GloCube+",
                "freezing_device": "Vitrobot Mark IV",
            },
            request_token=uuid4(),
            experiment_reference="EXCEL-TEST",
        )

    def workbook(self):
        return export_workbook(actor=self.staff, grids=Grid.objects.active())

    def edited_workbook(self, edit):
        book = load_workbook(BytesIO(self.workbook()))
        edit(book)
        output = BytesIO()
        book.save(output)
        book.close()
        return output.getvalue()

    def payload(self, content=None):
        return read_workbook(BytesIO(content or self.workbook()), filename="synthetic.xlsx")

    def new_workbook(self):
        """Give exported rows explicit new identities, simulating another installation."""

        def edit(book):
            owners = book["Owners"]
            owners.cell(2, 1, "newx")
            owners.cell(2, 2, "New synthetic owner")
            key = str(uuid4())
            book["Sessions"].cell(2, 1, key)
            book["Sessions"].cell(2, 2, str(uuid4()))
            sheet = book["Grids"]
            headers = {cell.value: cell.column for cell in sheet[2]}
            for number, row in enumerate(range(3, sheet.max_row + 1), 1):
                sheet.cell(row, headers["Grid ID"], f"newx-{number:04d}")
                sheet.cell(row, headers["Owner code"], "newx")
                sheet.cell(row, headers["Sample owner"], "New synthetic owner")
                sheet.cell(row, headers["Session"], key)

        return self.edited_workbook(edit)

    def new_records(self):
        return self.payload(self.new_workbook())

    def hand_workbook(self):
        book = load_workbook(BytesIO(self.new_workbook()))
        del book["Sessions"]
        del book["Read me"]
        sheet = book["Grids"]
        headers = {cell.value: cell.column for cell in sheet[2]}
        for row in range(3, sheet.max_row + 1):
            sheet.cell(row, headers["Session"], "session-1")
        output = BytesIO()
        book.save(output)
        book.close()
        return output.getvalue()

    def test_hand_entry_uses_plain_labels_without_keys_or_snapshot_metadata(self):
        payload = self.payload(self.hand_workbook())
        report = preview_import(actor=self.staff, payload=payload)
        self.assertEqual(report["new_sessions"], 1)
        self.assertTrue(report["warnings"])
        import_workbook(actor=self.staff, payload=payload)
        first = Grid.objects.get(grid_number="newx-0001")
        second = Grid.objects.get(grid_number="newx-0002")
        self.assertEqual(first.session_id, second.session_id)
        self.assertEqual(first.session.defaults, {})
        self.assertEqual(first.sample_volume_ul, self.session.grids.first().sample_volume_ul)
        self.assertEqual(str(first.drain_time_s), "1.25")
        self.assertEqual(first.carbon_description, "graphene")
        self.assertEqual(first.carbon_thickness_layers, 2)
        self.assertEqual(first.glow_device, "Quorum – GloCube+")
        self.assertEqual(first.freezing_device, "Vitrobot Mark IV")
        # Re-saving Excel changes the file checksum, not the identity of its grids.
        payload["sha256"] = "different-file-checksum"
        self.assertEqual(import_workbook(actor=self.staff, payload=payload)["existing_grids"], 2)

    def test_manual_labels_are_file_local_and_never_identify_an_unrelated_session(self):
        payload = self.payload(self.hand_workbook())
        import_workbook(actor=self.staff, payload=payload)
        first_session = Grid.objects.get(grid_number="newx-0001").session_id
        for index, row in enumerate(payload["grids"], 3):
            row["grid_number"] = f"newx-{index:04d}"
        import_workbook(actor=self.staff, payload=payload)
        second_session = Grid.objects.get(grid_number="newx-0003").session_id
        self.assertNotEqual(first_session, second_session)

    def test_a_manual_label_cannot_combine_existing_sessions(self):
        payload = self.payload(self.hand_workbook())
        payload["grids"][1]["session_key"] = "session-2"
        import_workbook(actor=self.staff, payload=payload)
        payload["grids"][1]["session_key"] = "session-1"
        with self.assertRaisesMessage(ValidationError, "different existing sessions"):
            preview_import(actor=self.staff, payload=payload)

    def test_blank_template_is_available_to_staff_with_hidden_transfer_keys(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("registry:excel_template"))
        book = load_workbook(BytesIO(response.content))
        self.assertTrue(book["Sessions"].column_dimensions["B"].hidden)
        self.assertEqual(book["Grids"].max_row, 2)
        book.close()
        self.assertEqual(self.payload(response.content)["grids"], [])

    def test_date_strings_default_to_stockholm_noon_with_seasonal_offsets(self):
        baseline = self.new_records()
        for index, (value, utc_hour) in enumerate([("2026-01-15", 11), ("2026-07-15", 10)]):
            with self.subTest(date=value):
                payload = copy.deepcopy(baseline)
                payload["sessions"][0]["session_key"] = str(uuid4())
                for number, row in enumerate(payload["grids"], index * 10 + 1):
                    row["grid_number"] = f"newx-{number:04d}"
                    row["prepared_at"] = value
                # Facility time must not depend on a viewer's active timezone.
                with timezone.override("UTC"):
                    report = import_workbook(actor=self.staff, payload=payload)
                grid = Grid.objects.get(grid_number=payload["grids"][0]["grid_number"])
                stored = grid.session.prepared_at
                local = timezone.localtime(stored, ZoneInfo("Europe/Stockholm"))
                self.assertEqual(local.date().isoformat(), value)
                self.assertEqual((local.hour, local.minute, local.second), (12, 0, 0))
                self.assertEqual(stored.hour, utc_hour)
                self.assertTrue(
                    any("12:00 Europe/Stockholm" in message for message in report["warnings"])
                )

    def test_excel_date_cells_also_default_to_local_noon(self):
        book = load_workbook(BytesIO(self.new_workbook()))
        sheet = book["Grids"]
        headers = {cell.value: cell.column for cell in sheet[2]}
        for row in range(3, sheet.max_row + 1):
            sheet.cell(row, headers["Preparation date and time"], date(2026, 7, 15))
        content = BytesIO()
        book.save(content)
        book.close()
        payload = self.payload(content.getvalue())
        self.assertEqual(payload["grids"][0]["prepared_at"], "2026-07-15")
        import_workbook(actor=self.staff, payload=payload)
        local = timezone.localtime(Grid.objects.get(grid_number="newx-0001").session.prepared_at)
        self.assertEqual(local.hour, 12)

    def test_invalid_dates_and_times_without_offsets_are_rejected(self):
        for value in ["2026-02-30", "2026-13-01", "2026-7-15", "2026-07-15T10:00:00"]:
            payload = self.new_records()
            for row in payload["grids"]:
                row["prepared_at"] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                preview_import(actor=self.staff, payload=payload)

    def test_blank_preparation_dates_remain_unknown(self):
        payload = self.new_records()
        for row in payload["grids"]:
            row["prepared_at"] = ""
        import_workbook(actor=self.staff, payload=payload)
        self.assertIsNone(Grid.objects.get(grid_number="newx-0001").session.prepared_at)

    def test_preview_is_read_only_and_import_is_atomic_audited_and_repeatable(self):
        payload = self.new_records()
        before = (Grid.objects.count(), AuditEvent.objects.count())
        report = preview_import(actor=self.admin, payload=payload)
        self.assertEqual(report["new_grids"], 2)
        self.assertEqual((Grid.objects.count(), AuditEvent.objects.count()), before)
        result = import_workbook(actor=self.admin, payload=payload)
        self.assertEqual(result["new_grids"], 2)
        grids = Grid.objects.filter(grid_number__startswith="newx-")
        self.assertEqual(grids.count(), 2)
        grid = grids.first()
        self.assertEqual(grid.sample_volume_ul, self.session.grids.first().sample_volume_ul)
        self.assertEqual(grid.hold_time_s, 0)
        self.assertEqual(grid.session.defaults, self.session.defaults)
        self.assertEqual(grid.session.prepared_at, self.session.prepared_at)
        self.assertEqual(grid.session.prepared_by, self.staff)
        self.assertTrue(AuditEvent.objects.filter(source="excel", entity_type="Grid").exists())
        repeated = import_workbook(actor=self.admin, payload=payload)
        self.assertEqual(repeated["new_grids"], 0)
        self.assertEqual(repeated["existing_grids"], 2)
        next_session = create_preparation_session(
            actor=self.staff,
            owner=grid.session.owner,
            prepared_at=timezone.now(),
            grid_count=1,
            preparation={},
            request_token=uuid4(),
        )
        self.assertEqual(next_session.grids.get().grid_number, "newx-0003")

    def test_grouped_headers_and_numeric_cells_match_the_current_layout(self):
        book = load_workbook(BytesIO(self.workbook()))
        sheet = book["Grids"]
        self.assertEqual(
            [cell.value for cell in sheet[1] if cell.value], [title for title, _ in GRID_GROUPS]
        )
        headers = {cell.value: cell.column for cell in sheet[2]}
        volume = sheet.cell(3, headers["Sample volume (µL)"])
        self.assertEqual(volume.data_type, "n")
        self.assertEqual(volume.number_format, "0.00")
        self.assertEqual(sheet.freeze_panes, "D3")
        column = 1
        for index, (_, names) in enumerate(GRID_GROUPS):
            heading, body = GROUP_COLORS[index % len(GROUP_COLORS)]
            self.assertEqual(sheet.cell(1, column).fill.fgColor.rgb[-6:], heading)
            self.assertEqual(sheet.cell(2, column).fill.fgColor.rgb[-6:], heading)
            self.assertEqual(sheet.cell(3, column).fill.fgColor.rgb[-6:], body)
            column += len(names)
        book.close()

    def test_export_includes_current_storage_and_transfer_history(self):
        grid = self.session.grids.first()
        dewar, _ = Dewar.objects.get_or_create(name="Dewar 1")
        cane, _ = Cane.objects.get_or_create(dewar=dewar, name="Cane 1")
        puck, _ = Puck.objects.get_or_create(cane=cane, color="green", defaults={"in_dewar": True})
        box_type = GridBoxType.objects.create(
            code="excel-box",
            name="Excel box",
            svg="excel-box.svg",
            layout={"unclipped": {"capacity": 4, "clipped": False}},
        )
        box = register_box(
            actor=self.staff,
            name="excel-transfer-box",
            box_type_id=box_type.pk,
            puck_id=puck.pk,
        )
        in_cci_grid = self.session.grids.exclude(pk=grid.pk).first()
        in_cci_box = register_box(
            actor=self.staff,
            name="excel-cci-box",
            box_type_id=box_type.pk,
            puck_id=puck.pk,
        )
        place_grid(
            actor=self.staff,
            grid_id=in_cci_grid.pk,
            slot_id=in_cci_box.slots.get(side="unclipped", position=1).pk,
            clipped=False,
            expected_version=in_cci_grid.version,
            occurred_at=timezone.now(),
        )
        slot = box.slots.get(side="unclipped", position=1)
        now = timezone.now()
        place_grid(
            actor=self.staff,
            grid_id=grid.pk,
            slot_id=slot.pk,
            clipped=False,
            expected_version=grid.version,
            occurred_at=now,
        )
        box.refresh_from_db()
        change_box(
            actor=self.staff,
            box_id=box.pk,
            expected_version=box.version,
            action="transfer",
            occurred_at=now + timedelta(minutes=1),
            transfer_destination="Partner laboratory",
        )

        book = load_workbook(BytesIO(self.workbook()))
        sheet = book["Grids"]
        headers = {cell.value: cell.column for cell in sheet[2]}
        row = next(
            number
            for number in range(3, sheet.max_row + 1)
            if sheet.cell(number, headers["Grid ID"]).value == grid.grid_number
        )
        self.assertEqual(sheet.cell(row, headers["Clipped"]).value, "No")
        self.assertEqual(
            sheet.cell(row, headers["Storage status"]).value,
            "Transferred to Partner laboratory",
        )
        self.assertIsNone(sheet.cell(row, headers["Dewar"]).value)
        self.assertIsNone(sheet.cell(row, headers["Cane"]).value)
        self.assertIsNone(sheet.cell(row, headers["Puck"]).value)
        self.assertEqual(sheet.cell(row, headers["Gridbox type"]).value, "Excel box")
        self.assertEqual(sheet.cell(row, headers["Gridbox"]).value, box.name)
        self.assertEqual(sheet.cell(row, headers["Slot"]).value, "1")
        history = sheet.cell(row, headers["Storage history"]).value
        self.assertIn("stored: excel-transfer-box / 1", history)
        self.assertIn("transferred to Partner laboratory", history)
        cci_row = next(
            number
            for number in range(3, sheet.max_row + 1)
            if sheet.cell(number, headers["Grid ID"]).value == in_cci_grid.grid_number
        )
        self.assertEqual(sheet.cell(cci_row, headers["Storage status"]).value, "At CCI")
        self.assertEqual(sheet.cell(cci_row, headers["Dewar"]).value, "Dewar 1")
        self.assertEqual(sheet.cell(cci_row, headers["Cane"]).value, "Cane 1")
        self.assertEqual(sheet.cell(cci_row, headers["Puck"]).value, "Green")
        self.assertEqual(sheet.cell(cci_row, headers["Gridbox"]).value, in_cci_box.name)
        book.close()

    def test_unplaced_grid_has_unknown_storage_status(self):
        content = self.workbook()
        book = load_workbook(BytesIO(content))
        sheet = book["Grids"]
        headers = {cell.value: cell.column for cell in sheet[2]}
        self.assertEqual(sheet.cell(3, headers["Storage status"]).value, "Unknown — needs review")
        self.assertIsNone(sheet.cell(3, headers["Gridbox"]).value)
        book.close()

    def test_save_failure_rolls_back_new_owners_sessions_grids_and_audit(self):
        payload = self.new_records()
        before = (
            Grid.objects.count(),
            SampleOwner.objects.count(),
            PreparationSession.objects.count(),
            AuditEvent.objects.count(),
        )
        with patch("registry.excel_import.record_audit", side_effect=RuntimeError("Test failure")):
            with self.assertRaises(RuntimeError):
                import_workbook(actor=self.staff, payload=payload)
        self.assertEqual(
            (
                Grid.objects.count(),
                SampleOwner.objects.count(),
                PreparationSession.objects.count(),
                AuditEvent.objects.count(),
            ),
            before,
        )

    def test_missing_owners_conflicting_owners_and_inconsistent_session_metadata_are_errors(self):
        payload = self.new_records()
        for change, message in [
            (lambda data: data["owners"].clear(), "missing"),
            (lambda data: data["grids"][1].update(experiment_reference="different"), "identical"),
            (lambda data: data["grids"][0].update(session_key=""), "Session label"),
            (lambda data: data["grids"][0].update(sample_volume_ul="1.234"), "decimal"),
            (lambda data: data["grids"][0].update(sample_volume_ul=True), "TRUE"),
        ]:
            candidate = copy.deepcopy(payload)
            change(candidate)
            with self.subTest(message=message), self.assertRaisesMessage(ValidationError, message):
                preview_import(actor=self.staff, payload=candidate)
        SampleOwner.objects.create(code="newx", name="Different owner")
        with self.assertRaisesMessage(ValidationError, "Owner conflict"):
            import_workbook(actor=self.staff, payload=payload)

    def test_export_includes_every_filtered_page(self):
        create_preparation_session(
            actor=self.staff,
            owner=self.owner,
            prepared_at=timezone.now(),
            grid_count=51,
            preparation={"sample_description": "Pagination sample"},
            request_token=uuid4(),
        )
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("registry:excel_export"), {"q": "Pagination sample", "page": 2}
        )
        self.assertEqual(len(read_workbook(BytesIO(response.content))["grids"]), 51)

    def test_bad_files_headers_and_expired_previews_return_useful_errors(self):
        with self.assertRaisesMessage(ValidationError, "valid .xlsx"):
            self.payload(b"not an Excel file")

        def edit(book):
            book["Grids"].cell(2, 1, "Wrong header")

        with self.assertRaisesMessage(ValidationError, "headings"):
            self.payload(self.edited_workbook(edit))
        self.client.force_login(self.staff)
        url = reverse("registry:excel_import")
        response = self.client.post(
            url, {"workbook": SimpleUploadedFile("test.xlsx", self.workbook())}
        )
        token = response.context["preview_token"]
        session = self.client.session
        session["registry_excel_preview"]["created_at"] = 0
        session.save()
        response = self.client.post(url, {"action": "confirm", "preview_token": token})
        self.assertContains(response, "preview the workbook again")

    def test_unchanged_export_is_a_noop_and_edited_grid_conflicts(self):
        payload = self.payload()
        self.assertEqual(import_workbook(actor=self.admin, payload=payload)["existing_grids"], 2)
        grid = self.session.grids.first()
        update_grid_preparation(
            actor=self.staff,
            grid_id=grid.pk,
            expected_version=grid.version,
            preparation={"notes": "Changed after export"},
        )
        with self.assertRaisesMessage(ValidationError, "conflict"):
            import_workbook(actor=self.admin, payload=payload)
        self.assertEqual(Grid.objects.get(pk=grid.pk).notes, "Changed after export")

    def test_filtered_export_does_not_require_or_change_copied_from_relationships(self):
        parent, child = self.session.grids.order_by("pk")
        child.copied_from_grid = parent
        child.save(update_fields=["copied_from_grid"])
        content = export_workbook(actor=self.staff, grids=Grid.objects.filter(pk=child.pk))
        book = load_workbook(BytesIO(content))
        self.assertNotIn("Copied from grid ID", [cell.value for cell in book["Grids"][2]])
        book.close()
        result = import_workbook(actor=self.staff, payload=self.payload(content))
        self.assertEqual(result["existing_grids"], 1)
        child.refresh_from_db()
        self.assertEqual(child.copied_from_grid_id, parent.pk)

    def test_invalid_measurements_and_duplicate_identifiers_fail_before_writes(self):
        def edit(book):
            sheet = book["Grids"]
            headers = {cell.value: cell.column for cell in sheet[2]}
            sheet.cell(3, headers["Sample volume (µL)"], -1)
            sheet.cell(4, headers["Grid ID"], sheet.cell(3, headers["Grid ID"]).value)

        before = Grid.objects.count()
        with self.assertRaises(ValidationError):
            preview_import(actor=self.admin, payload=self.payload(self.edited_workbook(edit)))
        self.assertEqual(Grid.objects.count(), before)

    def test_export_writes_formula_like_text_as_literal_text_and_import_rejects_formulas(self):
        Grid.objects.filter(session=self.session).update(notes='=HYPERLINK("test")')
        book = load_workbook(BytesIO(self.workbook()))
        headers = {cell.value: cell.column for cell in book["Grids"][2]}
        self.assertEqual(book["Grids"].cell(3, headers["Grid notes"]).data_type, "s")
        book.close()

        def edit(book):
            book["Grids"].cell(3, headers["Grid notes"], "=1+1")

        with self.assertRaisesMessage(ValidationError, "formula"):
            self.payload(self.edited_workbook(edit))

    def test_unknown_operator_stays_unknown_and_identifier_only_rows_are_skipped(self):
        payload = self.new_records()
        for row in payload["grids"]:
            row["prepared_by"] = "not-a-local-account"
        payload["grids"].append({"grid_number": "EMPTY-0001", "_row": 4})
        report = import_workbook(actor=self.admin, payload=payload)
        self.assertEqual(report["skipped_rows"], 1)
        self.assertTrue(report["warnings"])
        self.assertIsNone(Grid.objects.get(grid_number="newx-0001").session.prepared_by)
        self.assertFalse(Grid.objects.filter(grid_number="EMPTY-0001").exists())
        self.assertFalse(User.objects.filter(username="not-a-local-account").exists())

    def test_archived_ids_cannot_be_imported_and_archive_is_excluded_from_export(self):
        grid = self.session.grids.first()
        payload = self.payload()
        DeletedGrid.objects.create(grid=grid, deleted_by=self.admin)
        with self.assertRaisesMessage(ValidationError, "archived"):
            preview_import(actor=self.admin, payload=payload)
        self.assertEqual(len(self.payload()["grids"]), 1)

    def test_permissions_apply_to_services_and_http_upload_requires_preview_and_csrf(self):
        payload = self.payload()
        with self.assertRaises(PermissionDenied):
            import_workbook(actor=self.outsider, payload=payload)
        with self.assertRaises(PermissionDenied):
            export_workbook(actor=self.outsider, grids=Grid.objects.all())
        url = reverse("registry:excel_import")
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(url), "Preview import")
        self.assertEqual(self.client.post(url, {"action": "confirm"}).status_code, 200)
        upload = SimpleUploadedFile("synthetic.xlsx", self.new_workbook())
        response = self.client.post(url, {"workbook": upload})
        self.assertContains(response, "Confirm import")
        token = response.context["preview_token"]
        self.assertRedirects(
            self.client.post(url, {"action": "confirm", "preview_token": token}),
            reverse("registry:grid_list"),
        )
        self.assertEqual(Grid.objects.filter(grid_number__startswith="newx-").count(), 2)
        self.assertEqual(
            AuditEvent.objects.filter(entity_type="ExcelImport").get().actor, self.staff
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(url, {"action": "confirm"}).status_code, 403)

    def test_registry_access_allows_export_but_import_requires_cci_membership(self):
        administrator = User.objects.create_superuser(username="export-only-admin")
        content = export_workbook(actor=administrator, grids=Grid.objects.all())
        self.assertEqual(len(self.payload(content)["grids"]), 2)
        payload = self.payload()
        for command in [preview_import, import_workbook]:
            with self.assertRaisesMessage(PermissionDenied, "CCI staff member"):
                command(actor=administrator, payload=payload)
        self.client.force_login(administrator)
        registry = self.client.get(reverse("registry:grid_list"))
        self.assertContains(registry, "Export filtered grids to Excel")
        self.assertNotContains(registry, "Import Excel workbook")
        self.assertEqual(self.client.get(reverse("registry:excel_export")).status_code, 200)
        self.assertEqual(self.client.get(reverse("registry:excel_import")).status_code, 403)
        self.assertEqual(self.client.get(reverse("registry:excel_template")).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("registry:excel_import"), {"action": "confirm"}).status_code,
            403,
        )

    def test_import_membership_is_reloaded_even_for_a_stale_administrator(self):
        payload = self.payload()
        User.objects.filter(pk=self.admin.pk).update(is_cci_staff=False)
        for command in [preview_import, import_workbook]:
            with self.assertRaises(PermissionDenied):
                command(actor=self.admin, payload=payload)
        # Removing import rights does not remove this administrator's read access.
        self.assertEqual(
            len(self.payload(export_workbook(actor=self.admin, grids=Grid.objects.all()))["grids"]),
            2,
        )

    def test_export_intersects_supplied_rows_with_the_shared_visibility_boundary(self):
        first = self.session.grids.first()
        with patch("registry.excel.visible_grids", return_value=Grid.objects.filter(pk=first.pk)):
            content = export_workbook(actor=self.staff, grids=Grid.objects.all())
        self.assertEqual(
            [row["grid_number"] for row in self.payload(content)["grids"]], [first.grid_number]
        )

    def test_http_export_uses_search_and_property_filters_across_all_pages(self):
        self.client.force_login(self.staff)
        url = reverse("registry:excel_export")
        response = self.client.get(url, {"q": "no-such-sample"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(read_workbook(BytesIO(response.content))["grids"]), 0)
        params = {
            "filters-TOTAL_FORMS": "1",
            "filters-INITIAL_FORMS": "0",
            "filters-0-property": "sample_volume_ul",
            "filters-0-minimum": "4",
        }
        response = self.client.get(url, params)
        self.assertEqual(len(read_workbook(BytesIO(response.content))["grids"]), 0)
        params["filters-0-minimum"] = "3"
        response = self.client.get(url, params)
        self.assertEqual(len(read_workbook(BytesIO(response.content))["grids"]), 2)
        params["filters-0-minimum"] = "invalid"
        self.assertEqual(self.client.get(url, params).status_code, 400)
