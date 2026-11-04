# Instructions for Codex — CCI Cryo-EM Grid Registry

## Project context

Build an internal web application for six CCI staff members (three technically proficient, three less familiar with programming). Users need a quick form and an Excel-like table. All active CCI staff can view and edit all active grids; the preparation operator records attribution, not editing rights. Archived grids are read-only. Facility superusers manage accounts, existing owners and grants. External access is out of scope for v0.1 but must not require a schema rewrite later.

Current-format Excel import, preview and templates require the explicit CCI staff flag, even for superusers. Export follows existing registry viewing access and filters through the shared `visible_grids` boundary. Existing owner grants do not enable non-CCI browsing or restrict internal staff editing.

## Authoritative documents

- Read `docs/01_PRODUCT_BRIEF.md` for user workflow and MVP scope.
- Read `docs/02_SCHEMA_V0_1.md` for invariants and field structure.
- Read `docs/05_EXCEL_IMPORT_SPEC.md` before writing migrations or importer.
- Use `docs/06_ACCEPTANCE_TESTS.md` to determine what must be tested.
- Consult `docs/07_OPEN_DECISIONS.md`; do not guess unsettled scientific conventions.

If code and specification conflict, raise the discrepancy and propose an explicit documentation update. Do not silently change agreed behavior.

## Coding expectations

- Use the selected prototype stack: **Python 3.13, Django 5.2, PostgreSQL 17**, local Django accounts, Conda, server-rendered forms and minimal JavaScript. Add infrastructure or table libraries only for a demonstrated need.
- Keep business rules in a testable service layer, separate from forms/views/API endpoints.
- Implement **authorization server-side**, including bulk edits and object-level actions. Hiding UI controls is insufficient.
- Use a stable internal user primary key; decouple sample ownership from login accounts and from authentication mechanisms.
- Treat grid IDs as immutable, globally unique, and transactionally allocated. Preserve historical `CCI-...` values during import.
- Store the **session-default snapshot** separately from each independently editable grid's actual preparation values.
- Hand-entered Excel files use plain Session labels; internal keys are automatic. If original shared defaults are unknown, preserve an empty snapshot rather than inventing defaults from the first grid. The current format excludes copied-from links; the original combined-field workbook importer is deferred.
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
- Use **Europe/Stockholm** for facility time. Date-only imports explicitly default to noon on that date and report it in preview; blank dates remain unknown.
- Keep destructive operations restricted; use deactivation, correction records, or explicit archive rather than silently deleting history.
- Expose export capabilities and do not depend on proprietary database functionality unless justified.

## Review and Git workflow

- Develop features on a branch from current `main`. When preparing a PR, commit/push the branch and provide a GitHub compare link plus Markdown title/description. Leave PR creation to the user through the website.
- Push documentation-only changes directly to `main` when the user explicitly authorizes it; do not infer a blanket exception for other work.
- Keep code readable, with comments explaining business rules and platform choices. Do not add compatibility layers for superseded disposable test data unless needed for an agreed workflow.
- Linux/WSL integration and simulated Windows-layout tests pass. A colleague confirmed native Windows app startup and repeatable stop; on that setup Ctrl+C stopped both the app and PostgreSQL. A full Windows `python dev.py check` run and remaining native acceptance checks are still pending. Do not claim complete Windows validation without that evidence.
