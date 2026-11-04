# Architecture, authentication, authorization, and UI

**Version:** v0.1 working architecture\
**Last reviewed:** 2026-11-04\
**Status:** Implemented preparation/Excel baseline; physical handling and shared hosting remain planned

## 1. Selected prototype architecture

```mermaid
flowchart TB
    U[CCI staff web browser] --> W[Django web application]
    W --> S[Application service layer]
    W --> A[Django auth / identity adapter]
    A -. future .-> I[Institutional OIDC / external IdP]
    S --> D[(PostgreSQL)]
    S --> J[Excel import/export service]
    J --> F[Private XLSX data files]
    S -. future .-> O[OMERO / OMERO.figure]
    S -. future .-> L[Local document extraction / LLM]
```

**Prototype baseline:** Django 5.2 LTS + PostgreSQL 17, server-rendered forms and a plain HTML table. Add HTMX or a table library after workflow testing demonstrates the need. See the [prototype-first roadmap](04_DEVELOPMENT_ROADMAP.md) for delivery gates and local authentication. Use Django admin for *internal administration*, not necessarily as the final staff-facing workflow. Alternatives previously considered (Grist/eLabFTW) may still be worthwhile if custom development proves too heavy, but the state-transition and permission requirements lean toward Django.

Why this stack:

- Python is familiar to CCI's technical staff and fits later OMERO and document-processing integration.
- Django provides ORM, migrations, forms, admin, sessions, authentication backends, CSRF support, and permission hooks.
- PostgreSQL provides reliable transactions and unique constraints for numbering and storage occupancy.
- A small staff-facing web UI can be designed for the six-person team rather than forcing all users to navigate database tables.

**Avoid needless infrastructure initially:** no microservices, message broker, search cluster, Redis, Kubernetes, or separate API gateway required for the first pilot. Docker Compose can be an optional deployment convenience, not a functional requirement. Expose an API only if a real integration needs it.

The local runtime uses Conda (`environment.yml`) and includes PostgreSQL tools so Docker is optional. See the README for initialization, login and tests. The initial user model separates `is_cci_staff` (registry membership) from Django `is_staff` (admin access).

## 2. Current code organization

```text
config/                 # project settings / URL routing
registry/
  models.py             # preparation records, archive markers, audit and vocabulary
  services.py           # registration, grid edits, archive and admin commands
  permissions.py        # active staff, visible rows and explicit import permission
  forms.py, views.py    # staff forms and browse/detail routes
  preparation.py        # shared preparation fields, groups and normalization
  identifiers.py        # per-owner suffix encoding and limits
  tables.py, filters.py # registry columns and typed search/filter selection
  excel.py              # current workbook format and file I/O
  excel_import.py       # preview plan and atomic audited import
  excel_views.py        # downloads and two-step upload/confirmation
  suggestion_import.py # vocabulary seeding; not the legacy grid importer
  management/commands/ # generated field reference and suggestion seeder
  migrations/           # schema changes and PostgreSQL history guards
  tests.py, test_*.py   # models, services, migrations, permissions and HTTP tests
accounts/               # custom User, authentication and account administration
templates/registry/     # grouped forms, tables, details and history
static/                 # CSS and small workflow scripts
scripts/                # local configuration, platform tools and PostgreSQL launcher
dev.py                  # one-command start/check/stop
```

Keep these small modules readable; split them only when the code needs it.
StorageLocation/GridEvent services are not implemented. Centralize authorization
and business rules so HTTP and direct service calls follow the same policy.

## 3. Authentication should be replaceable

**Initial pilot:** Django local user accounts, strong passwords, server-managed sessions, HTTPS for non-local deployment, administrators capable of creating/deactivating accounts. Only six CCI accounts are needed initially.

**Later:** OIDC or another standards-based institutional identity provider (possibly university SSO / Entra ID). BankID is used in some institutional contexts but should **not** become a hard dependency; international collaborators need non-Swedish options.

The custom `accounts.User(AbstractUser)` was established in the first migration;
keep its stable internal primary key as the FK target. Future external identities
need a separate mapping; do not replace that key with an email or IdP subject.

Do not enable external registrations automatically. For the future, a researcher account should require CCI approval and explicit assigned access.

## 4. Authorization and roles

**Internal CCI access is shared** (confirmed 2026-11-04):

- Active CCI staff and facility administrators can view, register, export
  and edit all active grids. Preparation operator identity is attribution.
- Import, preview and the import template explicitly require the CCI staff flag,
  even for administrators. Export requires registry viewing access and uses its
  shared row-visibility boundary; a supplied queryset cannot expand that access.
- Every mutation is audited with actor, time and relevant before/after values.
- Archived records remain read-only. Archiving requires the actor's own password.
- Account management and editing existing owner profiles/grants remain admin-only.
- New owner registration/import creates no accounts or automatic grants.
- OwnerAccessGrant is retained for future external access, whose exact policy
  remains undecided. Existing grants do not limit internal CCI staff access.
- Inactive accounts and non-CCI non-administrators have no registry access. External users are not
  enabled by this change.

Legacy workbook interpretation and physical lifecycle actions remain separately
scoped work. Current-format Excel import is available to all active CCI staff.

**Security requirements:**

- Verify action authorization in server-side service/view before data mutation; querysets must be filtered for restricted users.
- Bulk mutation must authorize **every target row**, reject the whole operation (or clearly report per-row failures with no hidden partial success), and maintain audit events.
- Avoid IDOR/insecure object references: guessing a grid number must not grant write access.
- Show explicit permission errors rather than silently dropping unauthorized changes.
- Use anti-CSRF protections, session expiry, secure cookies, HTTPS, and least-privilege DB credentials.
- Restrict admin endpoints, log permission changes, and keep production debug mode off.

## 5. Staff-facing UI versus Django admin

### Main registry table

- Implemented: grid/sample/owner/experiment search, typed property filters, selectable
  columns, pagination and filtered XLSX export across all pages.
- Preparation editing uses View/edit links to individual forms. Inline/bulk editing,
  sorting controls and physical availability/location filters remain future work.
- Storage currently displays Unassigned; it is not a stored location/state projection.

### Session registration

1. Owner selector.
2. Preparation date/operator, optional experiment/project reference.
3. Shared preparation fields (grouped, numeric units labeled).
4. Count of grids to generate (1–100).
5. Explicitly select Create grids; Enter in an input does not submit the form.
6. Create the batch atomically and show its table with individual edit links.

This is one simple form. ID preview and a multi-step wizard are not implemented.

### Grid detail

- Implemented: immutable ID, owner/session context, grouped preparation editing,
  database audit history and password-confirmed archive.
- The physical summary is a fixed initial-state placeholder. Store/Move/Clip/Imaging/
  Return/Ship/Discard actions and physical event history remain planned.

### Admin

- Create/deactivate users, create owners and codes, assign/revoke grants, view import reports and audit records.
- Owner codes are automatic and stable after creation. Counters are managed by
  services, not a configuration screen; generic admin cannot edit scientific records.

## 6. Transactional domain services

Implement operations as testable service functions rather than putting state rules exclusively in view functions:

- `create_preparation_session(...)` — capture immutable snapshot; allocate N IDs safely; create N independent grids; all or nothing.
- `update_grid_preparation(...)` — enforce staff/archive/version rules, validate values and write audit history.
- `archive_grid(...)` — reauthenticate and atomically mark the record read-only with audit history.
- `preview_import(...)` / `import_workbook(...)` — validate current workbooks and apply a confirmed atomic import.

Planned after storage review:

- `bulk_update_grid_preparation(...)` — validate and audit a deliberately selected batch.
- `assign_storage(...)`, `move_grid(...)` — validate occupancy and lifecycle, append event, update current-state projection atomically.
- `clip_grid(...)` — mark clipped, record actor/time, optionally move to clipped location in same transaction.
- `remove_for_imaging(...)`, `record_imaging(...)`, `return_to_storage(...)` — keep imaging separate from disposal.
- `ship_grid(...)`, `discard_grid(...)` — remove from CCI available inventory, retain history.

Database transactions must guard against concurrent requests assigning the same slot or generating the same ID. Make service calls idempotent when requests can reasonably be retried (e.g., use a request idempotency token for session creation), to avoid accidental duplicate batches.

## 7. Audit / backups / operations

- Keep automatic created/modified timestamps, audited changes of scientific parameters, and append-only physical events.
- For imports, preserve the source filename/checksum, timestamp, row number, warnings, normalized values and original text (private access).
- Define PostgreSQL backups, retention policy, restore procedure and at least one tested restore before production use.
- No backup schedule, restore procedure or shared deployment is configured yet.
  Local data remains on the individual machine; Git stores code/docs, not the database.
  Filtered XLSX transfer is not a complete database backup.
- Set appropriate access controls on exports and database backups. Avoid public source control for raw research records.
- Keep versions pinned, configuration externalized, and document local startup / deployment steps.

## 8. Future integration boundaries

- **OMERO:** store stable server/image/dataset/figure IDs when implemented; no image blobs in registry required.
- **Local LLM:** separate background extraction pipeline from authorization and scientific source-of-truth. Its output is a *proposal for human review*, not an automatic edit to validated preparation data.
- **Public protocol publishing:** internal structured protocol model may eventually be exported to protocols.io, but publication is not part of this grid MVP.

## Grid deletion archive

Deleting a mistaken registration requires an authenticated active CCI account,
current-password verification on each submission and CSRF. The confirmation page
shows the selected grid ID, owner and session; no typed ID is required. Like
preparation editing, this action is permitted facility-wide for active CCI staff
and facility superusers. The
service locks the grid, checks its version and atomically creates a DeletedGrid
marker plus AuditEvent. Stored scientific records remain in the same PostgreSQL
database and become read-only; all normal registry/session views filter them out.
Original IDs and session relationships remain reserved. Archive views are read-only
and passwords are excluded from logs/history/forms. No purge or restore endpoint
is exposed. Physical lifecycle actions remain separate.


## Excel transfer implementation

`registry/excel.py` defines and reads/writes the current workbook format.
`registry/excel_import.py` builds a read-only validation plan and atomically applies
it after confirmation. `registry/excel_views.py` handles downloads/uploads; the
same `search_registry` function supplies the registry and export selection.
Workbooks stay out of Git. Preview data is held in the existing database-backed
Django session, scoped to the logged-in actor and an expiring confirmation token.
Confirmation revalidates current database contents. Imports serialize owner
creation/ID allocation and reserve imported natural IDs through existing unique
constraints. Failure rolls back owners, sessions, grids and audit together.
