"""Owner-scoped allocation, rollover, history preservation and retry safety."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from .identifiers import MAX_GRID_SEQUENCE, grid_suffix, suffix_sequence
from .models import AuditEvent, Grid, GridIdentifierCounter, PreparationSession, SampleOwner
from .services import create_preparation_session

User = get_user_model()


class GridIdentifierTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = User.objects.create_user(username="synthetic-operator", is_cci_staff=True)
        cls.owner = SampleOwner.objects.create(name="Alpha Owner", code="alow")
        cls.other_owner = SampleOwner.objects.create(name="Beta Owner", code="beow")

    def create(self, **overrides):
        arguments = dict(
            actor=self.actor,
            owner=self.owner,
            prepared_at=timezone.now(),
            grid_count=1,
            preparation={},
            request_token=uuid4(),
        )
        arguments.update(overrides)
        return create_preparation_session(**arguments)

    def set_next(self, number):
        GridIdentifierCounter.objects.update_or_create(
            namespace=f"owner:{self.owner.pk}", defaults={"next_number": number}
        )

    def test_suffix_boundaries_and_inverse(self):
        expected = {
            1: "0001",
            9999: "9999",
            10000: "a001",
            10998: "a999",
            10999: "b001",
            MAX_GRID_SEQUENCE: "z999",
        }
        for number, suffix in expected.items():
            self.assertEqual(grid_suffix(number), suffix)
            self.assertEqual(suffix_sequence(suffix), number)
        for invalid in [0, -1, True, MAX_GRID_SEQUENCE + 1]:
            with self.assertRaises(ValidationError):
                grid_suffix(invalid)
        for suffix in ["0000", "a000", "10000", "aa01", "!!!!"]:
            self.assertIsNone(suffix_sequence(suffix))

    def test_every_suffix_is_unique_and_four_characters(self):
        suffixes = {grid_suffix(number) for number in range(1, MAX_GRID_SEQUENCE + 1)}
        self.assertEqual(len(suffixes), MAX_GRID_SEQUENCE)
        self.assertTrue(all(len(suffix) == 4 and suffix == suffix.lower() for suffix in suffixes))

    def test_each_owner_starts_at_one_and_continues_across_sessions(self):
        first = self.create(grid_count=2)
        other = self.create(owner=self.other_owner)
        later = self.create()
        self.assertEqual(
            list(first.grids.values_list("grid_number", flat=True)), ["alow-0001", "alow-0002"]
        )
        self.assertEqual(other.grids.get().grid_number, "beow-0001")
        self.assertEqual(later.grids.get().grid_number, "alow-0003")

    def test_batches_cross_numeric_and_letter_boundaries(self):
        self.set_next(9998)
        session = self.create(grid_count=4)
        self.assertEqual(
            list(session.grids.values_list("grid_number", flat=True)),
            ["alow-9998", "alow-9999", "alow-a001", "alow-a002"],
        )
        self.set_next(10998)
        session = self.create(grid_count=2)
        self.assertEqual(
            list(session.grids.values_list("grid_number", flat=True)), ["alow-a999", "alow-b001"]
        )

    def test_exhaustion_does_not_create_a_partial_batch_or_consume_ids(self):
        self.set_next(MAX_GRID_SEQUENCE)
        with self.assertRaises(ValidationError):
            self.create(grid_count=2)
        self.assertFalse(Grid.objects.exists())
        self.assertFalse(PreparationSession.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertEqual(
            GridIdentifierCounter.objects.get(namespace=f"owner:{self.owner.pk}").next_number,
            MAX_GRID_SEQUENCE,
        )
        timestamp, token = timezone.now(), uuid4()
        last = self.create(prepared_at=timestamp, request_token=token)
        self.assertEqual(last.grids.get().grid_number, "alow-z999")
        # A retry is still safe even though no new IDs remain.
        self.assertEqual(self.create(prepared_at=timestamp, request_token=token).pk, last.pk)
        with self.assertRaises(ValidationError):
            self.create()
        self.assertEqual(Grid.objects.count(), 1)

    def test_existing_identifiers_are_preserved_and_matching_suffixes_are_reserved(self):
        original = self.create()
        for identifier in ["CCI-00001", "DEMO-0007", "ALOW-a123"]:
            Grid.objects.create(session=original, grid_number=identifier)
        self.assertEqual(self.create().grids.get().grid_number, "alow-a124")
        for identifier in ["CCI-00001", "DEMO-0007", "ALOW-a123", "alow-0001"]:
            self.assertTrue(Grid.objects.filter(grid_number=identifier).exists())

    def test_legacy_owner_code_is_not_silently_changed(self):
        owner = SampleOwner.objects.create(name="Legacy Owner", code="longer-code")
        with self.assertRaisesMessage(ValidationError, "four-character"):
            self.create(owner=owner)
        owner.refresh_from_db()
        self.assertEqual(owner.code, "longer-code")
        self.assertFalse(Grid.objects.exists())


class ConcurrentIdentifierRetries(TransactionTestCase):
    def test_duplicate_simultaneous_requests_allocate_only_one_batch(self):
        actor = User.objects.create_user(username="retry-operator", is_cci_staff=True)
        owner = SampleOwner.objects.create(name="Retry Owner", code="reow")
        token, timestamp = uuid4(), timezone.now()
        barrier = Barrier(2)

        def submit(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return create_preparation_session(
                    actor=actor,
                    owner=owner,
                    prepared_at=timestamp,
                    grid_count=8,
                    preparation={},
                    request_token=token,
                ).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            sessions = list(executor.map(submit, range(2)))
        self.assertEqual(len(set(sessions)), 1)
        self.assertEqual(Grid.objects.count(), 8)
        self.assertEqual(
            GridIdentifierCounter.objects.get(namespace=f"owner:{owner.pk}").next_number, 9
        )

    def test_reused_token_across_owners_reports_validation_error_without_partial_records(self):
        from unittest.mock import patch

        actor = User.objects.create_user(username="cross-owner-operator", is_cci_staff=True)
        owners = [
            SampleOwner.objects.create(name="First Owner", code="fiow"),
            SampleOwner.objects.create(name="Second Owner", code="seow"),
        ]
        token, timestamp = uuid4(), timezone.now()
        barrier = Barrier(2)
        original_save = PreparationSession.save

        def simultaneous_save(session, *args, **kwargs):
            barrier.wait(timeout=10)  # Both requests have validated before either inserts.
            return original_save(session, *args, **kwargs)

        def submit(owner):
            close_old_connections()
            try:
                try:
                    create_preparation_session(
                        actor=actor,
                        owner=owner,
                        prepared_at=timestamp,
                        grid_count=2,
                        preparation={},
                        request_token=token,
                    )
                    return "created"
                except ValidationError:
                    return "rejected"
            finally:
                close_old_connections()

        with patch.object(PreparationSession, "save", simultaneous_save):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(submit, owners))
        self.assertCountEqual(results, ["created", "rejected"])
        self.assertEqual(PreparationSession.objects.count(), 1)
        self.assertEqual(Grid.objects.count(), 2)
        self.assertEqual(
            GridIdentifierCounter.objects.filter(namespace__startswith="owner:").count(), 1
        )
