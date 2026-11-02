# Instructions for Codex — CCI Cryo-EM Grid Registry

## Project context

Build an internal web application for six CCI staff members (three technically proficient, three less familiar with programming). Users need a quick form and an Excel-like table. All CCI staff can view all grid records, while editing may be limited by sample-owner assignment. Admins manage accounts, owners, and grants. External access is out of scope for v0.1 but must not require a schema rewrite later.

## Authoritative documents

- Read `docs/01_PRODUCT_BRIEF.md` for user workflow and MVP scope.
- Read `docs/02_SCHEMA_V0_1.md` for invariants and field structure.
- Read `docs/05_EXCEL_IMPORT_SPEC.md` before writing migrations or importer.
- Use `docs/06_ACCEPTANCE_TESTS.md` to determine what must be tested.
- Consult `docs/07_OPEN_DECISIONS.md`; do not guess unsettled scientific conventions.

If code and specification conflict, raise the discrepancy and propose an explicit documentation update. Do not silently change agreed behavior.

## Coding expectations

- Prefer **Python, Django, PostgreSQL** unless the user deliberately chooses a different stack. This is a **recommendation**, not a decision already finalized.
- Keep business rules in a testable service layer, separate from forms/views/API endpoints.
- Implement **authorization server-side**, including bulk edits and object-level actions. Hiding UI controls is insufficient.
- Use a stable internal user primary key; decouple sample ownership from login accounts and from authentication mechanisms.
- Treat grid IDs as immutable, globally unique, and transactionally allocated. Preserve historical `CCI-...` values during import.
- Store the **session-default snapshot** separately from each independently editable grid's actual preparation values.
- Changes to the physical state are **events**, not free editing of status columns. Recording clipping, movement, imaging, shipping, or disposal must preserve an immutable history.
- Separate physical `GridEvent` history from `AuditEvent` (who corrected/edited a database record).
- Define an explicit state-transition service; reject impossible transitions and double-occupied storage positions.
- Use structured atomic fields and explicit units for measurable preparation conditions. Do not fabricate values when parsing source text.
- Make data imports repeatable/idempotent, validated, auditable, and dry-run capable. Never import blank preallocated identifiers as physical grids.
- Use human-readable error messages and fast workflows for nontechnical staff; avoid demanding detailed metadata that the Excel source does not possess.
- Avoid storing passwords, secrets, API tokens, or private laboratory records in Git. Use environment variables and provide `.env.example` without credentials.
- Write model, service, permission, and importer tests before considering a feature finished.

## Suggested incremental workflow

1. Explain the smallest vertical slice and files to change.
2. Implement models and migrations, then fixture/test data.
3. Implement service-layer commands and invariants.
4. Implement one usable form + one usable table for real staff workflow.
5. Add Excel import/export and event actions.
6. Review deployment/auth settings and back up/restore.
7. Update docs and run tests after each step.

Do not add local LLMs, OMERO integration, general protocol editors, or public protocols.io export in v0.1 without a separate scoped decision.

## Default development conventions

- Use Django migrations, Django test framework or pytest-django, type hints where helpful, and linting/formatting.
- Prefer `Decimal` rather than floating point for measurements; preserve original raw source text on import.
- Prefer UTC-aware timestamps, with localized UI display; distinguish event time from entry time.
- Keep destructive operations restricted; use deactivation, correction records, or explicit archive rather than silently deleting history.
- Expose export capabilities and do not depend on proprietary database functionality unless justified.
