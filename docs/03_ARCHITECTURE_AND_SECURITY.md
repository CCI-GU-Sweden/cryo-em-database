# Architecture, authentication, authorization, and UI

**Version:** v0.1 proposal  
**Date:** 2026-11-02  
**Status:** Local prototype baseline selected 2026-11-03; advanced UI and shared hosting follow workflow review

## 1. Proposed architecture

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

## 2. Code organization (suggested)

```text
config/                 # project settings / URL routing
registry/
  models/               # owners, sessions, grids, locations, events
  services/             # create_session, allocate_ids, move, clip, ship, discard, import
  selectors/            # authorized grid querysets and views
  forms/                # validated input / event forms
  views/                # staff web routes
  templates/registry/   # grouped forms, table, detail and history
  tests/                # models, services, permissions and views
accounts/               # user account config and owner-grant admin
imports/                # import parser, normalization, preview and report
```

This is a **suggestion**, not a strict directory mandate. Prefer a manageable repository structure over premature modularity. Centralize authorization and business rules to prevent inconsistent behavior between forms, table edits, and future API endpoints.

## 3. Authentication should be replaceable

**Initial pilot:** Django local user accounts, strong passwords, server-managed sessions, HTTPS for non-local deployment, administrators capable of creating/deactivating accounts. Only six CCI accounts are needed initially.

**Later:** OIDC or another standards-based institutional identity provider (possibly university SSO / Entra ID). BankID is used in some institutional contexts but should **not** become a hard dependency; international collaborators need non-Swedish options.

Keep a **stable internal AppUser ID** as the FK target. Associate external identities via a separately managed mapping rather than making email, BankID, or external subject IDs the primary key. If planning to use Django's custom user model, choose it **before running initial migrations**, because changing the user model afterward is expensive.

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

- Fast search and filters: ID, owner, experiment ref, sample, date, available status, clipped status, location.
- Hide long preparation columns by default; expandable groups: **Identity**, **Preparation**, **Storage**, **Lifecycle**.
- Safe editable cells for scientific parameters only; IDs and derived status read-only.
- Bulk edit selected rows, with a preview showing *exact grids and old/new values* before confirming.
- Export filtered results with stable field names and explicit units.

### Session wizard

1. Owner selector.
2. Preparation date/operator, optional experiment/project reference.
3. Shared preparation fields (grouped, numeric units labeled).
4. Count of grids to generate.
5. Preview ID allocation and defaults.
6. Confirm atomic creation; redirect to editable generated-grid table.

### Grid detail

- Summary: immutable grid ID, sample owner, session, current clipping/availability/imaging states, location.
- Individual preparation field editing.
- Dedicated **Store**, **Move**, **Clip**, **Remove for imaging**, **Mark imaged**, **Return**, **Ship**, **Discard** actions.
- Chronological event history and separate database audit history (admin-only where appropriate).
- Notes and experiment reference.

### Admin

- Create/deactivate users, create owners and codes, assign/revoke grants, view import reports and audit records.
- Owner code and identifier sequence configuration. Avoid routine editing of allocated IDs.

## 6. Transactional domain services

Implement operations as testable service functions rather than putting state rules exclusively in view functions:

- `create_preparation_session_and_grids(...)` — capture immutable snapshot; allocate N IDs safely; create N independent grids; all or nothing.
- `update_grid_preparation(...)` / future `bulk_update_grid_preparation(...)` — check active staff access and archive restrictions, validate values, write audit history.
- `assign_storage(...)`, `move_grid(...)` — validate occupancy and lifecycle, append event, update current-state projection atomically.
- `clip_grid(...)` — mark clipped, record actor/time, optionally move to clipped location in same transaction.
- `remove_for_imaging(...)`, `record_imaging(...)`, `return_to_storage(...)` — keep imaging separate from disposal.
- `ship_grid(...)`, `discard_grid(...)` — remove from CCI available inventory, retain history.

Database transactions must guard against concurrent requests assigning the same slot or generating the same ID. Make service calls idempotent when requests can reasonably be retried (e.g., use a request idempotency token for session creation), to avoid accidental duplicate batches.

## 7. Audit / backups / operations

- Keep automatic created/modified timestamps, audited changes of scientific parameters, and append-only physical events.
- For imports, preserve the source filename/checksum, timestamp, row number, warnings, normalized values and original text (private access).
- Define PostgreSQL backups, retention policy, restore procedure and at least one tested restore before production use.
- Set appropriate access controls on exports and database backups. Avoid public source control for raw research records.
- Keep versions pinned, configuration externalized, and document local startup / deployment steps.

## 8. Future integration boundaries

- **OMERO:** store stable server/image/dataset/figure IDs when implemented; no image blobs in registry required.
- **Local LLM:** separate background extraction pipeline from authorization and scientific source-of-truth. Its output is a *proposal for human review*, not an automatic edit to validated preparation data.
- **Public protocol publishing:** internal structured protocol model may eventually be exported to protocols.io, but publication is not part of this grid MVP.

## Grid deletion archive

Deleting a mistaken registration requires an authenticated active CCI account,
current-password verification on each submission and CSRF. The confirmation page
shows the selected grid ID, owner and session; no typed ID is required. This action is permitted facility-wide, unlike preparation editing. The
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
