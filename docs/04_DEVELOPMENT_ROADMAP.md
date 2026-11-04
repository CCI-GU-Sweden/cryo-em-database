# Development roadmap — CCI Cryo-EM Grid Registry

**Version:** v0.1\
**Last reviewed:** 2026-11-04\
**Approach:** incremental vertical slices with demoable features, tests, and real staff feedback.

## Current implementation — 2026-11-04

| Area | Current state |
|---|---|
| Local scaffold | Django/PostgreSQL, Conda, local accounts and one-command start/check/stop implemented |
| Preparation workflow | Owner codes, per-owner grid IDs, immutable session defaults and independent grid edits implemented |
| Browsing | Owners, sessions and grids; selectable registry columns and typed filters implemented |
| Permissions | All active CCI staff edit all active grids; operator is attribution. Import requires the CCI flag even for admins; export follows registry viewing access |
| Mistaken registrations | Password-confirmed archive and read-only Deleted grids implemented; restore/purge deferred |
| Current Excel transfer | Filtered XLSX export, colour groups, blank hand-entry template, plain Session labels, preview/confirmation and audited atomic import implemented |
| Facility time | Europe/Stockholm; date-only imports default to noon and report it; blank dates stay unknown |
| Windows launcher | Conda paths, password-file handling and startup options fixed; native Windows start/check/stop still needs colleague verification |
| Last full validation | 119 tests and all project checks passed on Linux/WSL; a fresh temporary PostgreSQL cluster also passed startup/authentication/shutdown with spaces/apostrophe in its path |

Remaining work includes initial physical storage/events, full lifecycle actions,
bulk/inline edits, original legacy workbook parsing, CSV/full-history exports,
shared deployment and backup/restore. Excel transfer is not a database backup.

**Next proposed slice:** finish native Windows verification and agree D03 with
staff using real examples of storage positions and occupancy. Then implement only
initial store/move actions with an immutable event history and atomic occupancy
checks. Do not guess the storage hierarchy or expand this slice to every lifecycle
action. Other scientific decisions remain in [the decision register](07_OPEN_DECISIONS.md).

## Guiding priorities

1. **Science/data integrity**: no lost IDs, no fabricated measurements, no contradictory storage states.
2. **Adoption**: nontechnical staff can perform the Excel workflow in a browser.
3. **Secure, replaceable identity**: start with local accounts; keep access grants independent of login provider.
4. **Minimal infrastructure**: avoid nonessential services.
5. **Extensibility**: later OMERO and knowledge-base features must not require rewriting core identity and inventory concepts.

## Local prototype decision — 2026-11-03

This decision established the prototype approach. The scaffold, registration and
current-format Excel transfer are now implemented. Full v0.1 acceptance criteria
remain the release target; evolve the model through migrations after staff feedback.

| Layer | Start with | Add after validation |
|---|---|---|
| Backend | Python 3.13, Django 5.2 LTS, psycopg 3; lock compatible patch versions when scaffolding | Supported-version upgrades as maintenance |
| Database | PostgreSQL 17 from the first migration, including tests | Indexes based on actual queries; shared hosting later |
| UI | Django forms/templates, plain HTML table and minimal CSS | HTMX or a spreadsheet library if staff trials demonstrate a need |
| Authentication | Local Django username/password login, session cookies, custom AbstractUser before first migration | Institutional SSO and explicit external identity mapping |
| Administration | Django admin for users, owners and access grants | Custom administration screens if useful |
| Runtime | Conda environment from `environment.yml`, including PostgreSQL tools for a local loopback database; Docker Compose remains optional | Internal HTTPS deployment with production app server |
| Verification | Django tests on PostgreSQL, Ruff and locked dependencies | Browser tests for advanced table interactions |
| Excel | openpyxl current-format XLSX import/export and synthetic test fixtures | Original legacy parser, CSV/full-history exports after domain review |

Django 5.2 has extended support through April 2028; schedule an upgrade before then. Sources: [Django supported releases](https://www.djangoproject.com/download/), [Django PostgreSQL backend](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes).

Local means browser and application on the same machine, bound to loopback. Create
individual accounts administratively; keep password hashing, CSRF and authenticated
mutations. Keep CCI membership separate from Django's admin-site access flag.
Verify shared CCI editing, non-CCI/inactive rejection, import's explicit CCI flag,
export visibility and archive protections. Owner grants do not restrict internal
CCI editing. SSO, public signup and email recovery remain outside this stage.

Use a clearly labeled prototype database and synthetic data. Excel remains authoritative until operational readiness. Resets require explicit agreement and apply only to disposable data; retain migrations in Git. Before retaining real records, establish backup/restore and correction procedures. Shared LAN access is a separate deployment step.

## Phase 0 — Local scaffold

**Status:** implemented and integration-tested on Linux/WSL; native Windows manual verification pending.

- Configure Django/PostgreSQL, the custom user model, dependency locking, Ruff and test commands.
- Document database startup, migrations, account creation and loopback app startup.
- Provide `.env.example` and repeatable synthetic demonstration data.

**Done when:** a developer starts the application, logs in and runs tests against PostgreSQL using documented commands.

## Phase 1 — First staff demo: register and inspect grids

**Status:** implemented, including later session browsing, filtering and archive refinements. ID preview and bulk/inline editing remain deferred.

- Implement SampleOwner, PreparationSession, Grid, OwnerAccessGrant and AuditEvent with the services needed for registration.
- Provide a simple session form: owner, preparation date/operator, optional reference, shared parameters and grid count.
- Atomically save the session, immutable defaults snapshot and independent grids.
- Display generated grids in a plain table; edit individual preparation fields through detail forms and display audit history.
- Preserve structured measurements, explicit units and unknown values. Storage remains unassigned in this slice.
- Route mutations through services, including admin actions; prevent generic admin edits to IDs and immutable snapshots.
- Test copying, failed-transaction rollback, unique IDs under concurrency, permissions and create/edit forms.

**Identifier decision (confirmed 2026-11-04):** new IDs use the four-character
sample-owner code and a separate per-owner sequence: `0001`–`9999`, then
`a001`–`a999`, `b001`–`z999`. Lock allocation transactionally and stop at exhaustion.
Preserve existing DEMO/CCI identifiers; do not allocate new DEMO IDs.

**Acceptance:** a colleague logs in, creates eight grids, edits two, reloads and
confirms that the other six and the session snapshot are unchanged. Demonstrate
atomic validation failures, audited edits by a second CCI member, and rejection
of inactive/non-CCI edits and archived-record changes.

## Phase 1a — Current-format Excel transfer

**Status:** implemented ahead of storage to support early data-model testing.

- Export the filtered active subset across all pages with all atomic preparation
  columns, original-style colour groups and supporting owner/session metadata.
- Supply a blank template with plain Session labels and automatic internal keys;
  original defaults stay unknown when not supplied.
- Preview missing owners, unchanged rows, conflicts and defaulted/unknown values;
  confirm an audited atomic import without overwrites or duplicate records.
- Require CCI membership for import; reuse registry visibility for export.
- Keep copied-from links, physical events and complete audit restoration outside
  this transfer format. Original legacy workbook parsing remains Phase 4 work.

## Phase 2 — Model review and initial physical storage

**Status:** not implemented; D03 must be confirmed before location validation.

- Review real fields, required inputs, session boundaries, units and form usability with staff; record decisions and migrations.
- Confirm D03 with examples of actual clipped and unclipped locations.
- Add StorageLocation and the initial GridEvent subset: store and move, with read-only current location and append-only history.
- Enforce occupancy in the database and update events/location atomically.
- Test occupied destinations, concurrent assignments, rollback and permissions.
- Preserve the existing version-based stale-edit protection when adding physical actions and simultaneous updates.

**Done when:** staff can assign and move a synthetic grid, see both locations in history and cannot double-book a slot. Review whether real storage fits the schema comfortably.

**Review gate:** proceed after registration and storage fit staff practice. Record observed friction and unresolved domain questions. Trial spreadsheet tooling only against concrete editing tasks.

## Phase 3 — Physical handling and inventory operations

**Status:** deferred until initial storage has been validated.

**Deliverables**

- Extend store/move with clip, remove for imaging, record imaging, return, ship and discard actions.
- Define corrections, backdated events and exceptional transition rules before exposing those operations.
- Current state and current location read-only projections in UI.
- Location occupancy checking, movement history, event chronology.
- Bulk selection and safe targeted actions where genuinely useful.
- Search/filter availability, clipped state, and last location.

**Done when:** a test scenario covers grid preparation → storage → clipping → move → imaging → discard; another covers shipment directly from storage; every event has an accurate history.

## Phase 4 — Original legacy workbook migration and richer export

**Status:** deferred. Current-format XLSX transfer is already implemented in Phase 1a.

**Remaining deliverables**

- Import parser for exact workbook headers (row 3) and source rows.
- Preview/dry-run that skips preallocated identifiers without actual grid data.
- Raw-value preservation, warnings for ambiguous/unknown units, duplicate detection.
- Reuse the explicit CCI import permission, with reviewed mappings and row-level reports; do not add an administrator-only restriction without a new decision.
- CSV/XLSX export with explicit headers and no implied scientific conversions.

**Done when:** the eight populated demonstration rows can be imported, inspected, searched, and exported without loss of their original information; repeated import cannot silently duplicate grids.

> Existing vocabulary seeding does not implement the legacy grid importer. Real
> legacy migration waits for mapping decisions and physical-event validation;
> ambiguous humidity, session membership and grid references must not be guessed.

## Phase 5 — Pilot with all six CCI staff

**Deliverables**

- Set up a protected internal deployment and backups.
- Run a real pilot with the colleague who maintains the Excel file and the remaining staff.
- Capture workflow friction (number of clicks, time to register 5–10 grids, edit, find, move, and clip).
- Review actual permission needs and optional field vocabulary.
- Iterate forms, table defaults, quick actions and documentation.

**Done when:** staff prefer the browser workflow for routine recording; data is correct; access controls have been tested; backup restore has been demonstrated.

## Phase 6 — Hardening and initial release

**Deliverables**

- Stable migrations and repeatable deploy process.
- Permission/race-condition tests, error handling, logging, time zones, user deactivation.
- Versioned release notes, operator manual, backup/runbook, export/restore pathway.
- Agree how to retire/retain the old Excel workbook to avoid dual sources of truth.

**Done when:** one supported application is the system of record; procedures for outages and export exist.

## Future milestones (not MVP commitments)

- Grid observation/outcome module for successful/failed preparations.
- OMERO image/dataset and OMERO.figure links, with access-control integration.
- External researcher accounts with limited read and lifecycle actions via institutional OIDC.
- Protocol documents and version/lineage records for LM/EM/cryo-EM.
- Local document extraction (e.g., Docling) and small local LLM for draft structured fields, subject to review.
- Public protocols.io export of selected reviewed protocols.

## Suggested Codex task breakdown

| Task | Status / dependency | Concrete output |
|---|---|---|
| T01 | Implemented; Windows manual check pending | Scaffold, Conda launcher, tests and run instructions |
| T02 | Implemented | Registration models, audit, admin and synthetic fixtures |
| T03 | Implemented | Owner-code and per-owner grid allocation; atomic session creation |
| T04 | Implemented for internal accounts | Shared staff editing, import/write boundary, export visibility and permission tests |
| T05 | Next proposed feature; requires D03 | Initial store/move models, services, UI and occupancy/concurrency tests |
| T06 | Implemented as a simple form | New session, independent grid editing, browse/filter screens; ID preview deferred |
| T07 | After T05 | Lifecycle actions and physical event history UI |
| T08 | After workflow review | Safe batch updates; add table tooling only if needed |
| T09a | Implemented | Current-format XLSX import/export, hand-entry template and provenance |
| T09b | Mapping decisions and storage/event review | Original legacy grid importer; vocabulary seeding alone is insufficient |
| T10 | Pilot after workflow/storage validation | Six-staff feedback, model review and permission/export checks |
| T11 | Before retaining operational records/shared hosting | Backup/restore, production settings and deployment runbook |

## Avoid these shortcuts

- No `owner_id` as sole authorization check at UI level.
- No auto-disposal on `imaged` without an explicit event.
- No rewriting historical IDs to new owner prefixes.
- No silent conversion of humidity `1` to `1%` or `100%`.
- No assuming workbook `JB002` identifies the real preparation session.
- No treating blank Excel rows with a grid number as real physical grids.
- No copying one session's live state across grids after creation.
