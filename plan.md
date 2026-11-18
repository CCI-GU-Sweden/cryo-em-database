# Dashboard integration roadmap

**Agreed:** 2026-11-16

**Status:** Stages 1 and 2 implemented and pushed. Stage 3 implemented and tested
locally; ORCID login and dashboard stock/review counts confirmed by Rafa.
Broader workflow acceptance and release checks remain in stage 4.

**Contract reference:** `Dashboard-django/MODULE_CONTRACT.md`, version 1, reviewed at dashboard commit `855a4d4`.

## Scope and ownership

Maintain one grid registry module that runs in two hosts:

- Standalone development: `python dev.py` starts the app and local PostgreSQL,
  using local username/password login. `python dev.py check` remains the local
  verification entry point. Routine scientific, storage and UI work requires
  neither the dashboard checkout nor ORCID credentials or network access.
- Dashboard deployment: install the registry as a versioned Django package in
  the dashboard process, sharing its configured user model, session, database
  connection and ORCID login. The dashboard owns account approval, roles,
  disabling users, deployment settings and module registration.

The module owns preparation records, sample owners, storage inventory, physical
events, registry auditing, permission enforcement, views, exports and migrations.
It must not depend on tickets, uploads, OMERO or other optional dashboard modules.
Sample ownership remains separate from login identity. Actor references use
Django's configured user model; names, email addresses and ORCID iDs are not
substitutes for the internal user primary key.

## Confirmed decisions

| Role | Initial registry access |
|---|---|
| Pending | No access; represented as an empty role, matching the dashboard. |
| Researcher (`researcher`) | No access initially. Future researcher workflows need an explicit policy. |
| Staff (`staff`) | CCI staff: shared grid, session, owner registration and inventory workflows. |
| Admin (`admin`) | Staff workflows plus registry administration. |

Inactive users have no access regardless of role. Django `is_staff` controls
Django admin-site access; it is not the shared Staff role. Dashboard role checks
must not assume that Admin means Django `is_superuser` or enables Django admin.

Sensitive actions require the signed-in authorized user to type `approve`.
This replaces password re-entry for grid deletion, grid status correction,
gridbox history correction and puck registration in both hosts. Match the word
after stripping surrounding whitespace; require lowercase `approve`.
Existing required correction reasons, CSRF protection, version/occupancy checks,
transactions and immutable history remain mandatory. This is deliberate action
confirmation, not identity reauthentication. Record the actor and action, not a
password. Login still uses a password locally and ORCID in the dashboard.

The dashboard starts with clean registry data and the agreed default storage
inventory. Do not copy prototype users or experimental grids into production.
Future full backup/restore and selective API/Excel transfers are separate work;
they must explicitly handle user references and historical attribution. Current
Excel export is not a full backup. Import stays hidden pending future review.

## Stage 1 — Align users, roles and sensitive-action confirmation

1. Add the shared role vocabulary to standalone accounts. Pending is empty;
   Staff and Admin grant registry access; Researcher does not.
2. Migrate existing local users explicitly: existing superusers become Admin,
   existing CCI members become Staff, and other accounts become Pending unless
   already explicitly classified. Preserve user IDs, passwords, attribution and
   active/disabled state. Stop using `is_cci_staff` as the authorization source.
3. Centralize staff/admin checks and reload current privileges for mutations.
   Cover views, direct services, owner/grant administration, exports and retained
   importer endpoints. Hidden import uses the same Staff/Admin access policy;
   the old special CCI-flag exception is superseded.
4. Replace password fields/checks on the four sensitive workflows with the typed
   approval field. Update forms, services, messages, tests and working docs.
5. Adapt local account administration and bootstrap so developers can create and
   manage the shared roles. Keep local login and `dev.py` working.

**Done when:** local Staff/Admin workflows work, Pending/Researcher/inactive users
are rejected server-side, wrong or missing approval cannot mutate data, correction
reasons and history remain intact, and all local checks pass. Stage 1 does not
require installation in the dashboard.

## Stage 2 — Extract the installable registry module

**Python alignment decision (2026-11-17):** Target Python 3.12 in both hosts.
The standalone Conda environment, package minimum and Ruff target follow that
version; keep Django 5.2 and PostgreSQL 17. Updating an existing local Conda
environment is an explicit developer action and does not reset its database.

**Beta baseline decision (2026-11-17):** Existing prototype databases are
disposable. Review old migrations and compatibility paths and remove those
needed only for obsolete prototype states. Preserve current scientific and
inventory invariants, immutable histories, authorization and their meaningful
tests. A fresh baseline must seed the agreed default storage inventory. Changing
the migration baseline requires recreating existing prototype databases; never
silently reset one on startup or migration.

The fresh baseline and removal of retired configuration/browser/snapshot
compatibility paths are implemented and tested. The runtime packaging slice is implemented locally; dashboard wiring remains stage 3.

Provide a local development reset command for repeated testing. Remove grids,
sessions, sample owners and registered gridboxes, including their associated
slots, physical events, archive/audit records, suggestions and identifier
counters. Preserve gridbox types, configured pucks, cane and dewar; restore puck
state consistently with the resulting empty inventory. Preserve user accounts by
default, with a separate explicit option to clear them when requested.
The command must identify its target and require explicit confirmation. The reset must target only the
verified checkout-local PostgreSQL cluster, never a dashboard deployment or
arbitrary configured database. First create and inspect a compressed PostgreSQL
backup in `.local/backups/`; fail before clearing anything if backup fails. Stop
the app to avoid writes between backup and reset. Do not expose a destructive web API.

1. Package the registry with its migrations, templates, CSS/JavaScript and SVGs.
   Use a unique Python package name and namespaced template/static paths.
2. Retain `config`, local accounts, launcher and PostgreSQL tooling as the
   standalone development host; exclude them from the deployed module package.
   Both repositories currently have an `accounts` package: only the host's
   accounts application may be installed in each running configuration.
3. Replace direct local-user imports with the configured user model. Keep host
   integration small and explicit: permission adapters, layout and navigation.
   Import the dashboard descriptor only in dashboard mode.
4. Use the fresh beta baseline: one accounts schema migration, one registry schema
   migration and one inventory/history migration. Obsolete prototype databases
   require a fresh database, not an upgrade or fake migration. Preserve PostgreSQL
   history guards. Module imports must have no setup or database side effects.

**Done when:** a built wheel contains every runtime asset; an installed standalone
host passes checks and starts via `dev.py`; ordinary module work has no dashboard
dependency. The module does not alter the host user model or global settings.

### Implemented slice — package and standalone host

- Package the runtime app as `cci_grids`, retaining Django app label `registry`,
  existing table names and the `registry` URL namespace. Update imports, app
  configuration, settings and tooling together.
- Move registry templates into the app's `templates/registry/` directory and
  runtime assets into its `static/cci_grids/` directory. Use a module-owned base
  template and update all static references, including seeded box-type SVG paths.
  The local host keeps its login/home templates and accounts.
- Add wheel metadata and explicit package data; exclude local configuration,
  user models and PostgreSQL tooling from the installed runtime module.
- Remove the remaining runtime import of the local account model. Keep
  standalone-only reset and documentation tools with the development host so the
  runtime package does not depend on `scripts` or repository documentation paths.
- Keep `python dev.py` and `python dev.py check` working directly from a checkout.
  Validate a built wheel's contents and rendering/static discovery from an
  installed copy outside the checkout, as well as the normal PostgreSQL suite.
- Refresh the local beta database path only through explicit instructions if
  seeded SVG paths change. Do not reset user data or edit the dashboard repository
  during this slice. Dashboard registration and layout integration are stage 3.

The runtime distribution is `cci-grids` (`cci_grids` Python package), retaining
the `registry` Django app label and URL namespace. Build/probe commands and the
existing-beta SVG-path migration are documented in README.md. No database reset or
dashboard changes are part of this slice.

## Stage 3 — Wire the dashboard contract

1. Add the version-1 DashboardModule descriptor and a namespaced landing route.
   The descriptor URL configuration mounts the registry prefix once.
2. Add an explicit dashboard enable setting, package pin and descriptor
   registration. Deploy the package; never depend on a sibling checkout at runtime.
3. Use dashboard users/roles and layout. Enforce Staff/Admin permissions on every
   page, action and overview endpoint, beyond hiding the overview card.
4. Review admin-only owner/grant management: provide authorized dashboard-facing
   management where the core does not install Django admin.
5. Use module-owned facility-time rendering/inputs for Europe/Stockholm without
   overriding global dashboard settings. Scope overview metrics to authorized users.

**Done when:** staff can enter the registry after dashboard ORCID login; Pending,
Researcher and disabled users cannot access direct module URLs; disabling the
module removes its routes/card and preserves data; unrelated modules still work.

### Implemented slice — local dashboard trial

- Register contract v1 at `cci_grids.dashboard_module.module`, with a single
  `/registry/` mount, Staff/Admin access and authorized CCI stock metrics.
- Select dashboard layout explicitly with `CCI_GRIDS_DASHBOARD`; keep registry
  CSS scoped to its content and preserve standalone layout and startup.
- Use Europe/Stockholm for registry form parsing, display, session labels and
  Excel dates without changing the dashboard's global timezone.
- Provide role-Admin owner/grant management inside the registry, using the
  existing audited services without requiring the Django admin application.
- Add an installed-wheel integration harness against the real dashboard user
  model on a disposable PostgreSQL test database. Keep all test accounts separate
  from the browser trial database.
- The local dashboard has an opt-in `DASHBOARD_GRIDS_ENABLED` registration and
  a locally installed wheel. Uploads, OMERO and tickets are disabled for this trial.
  A separate fresh PostgreSQL database starts with no users or grids and the
  default storage templates. Neither former database was cleared.

See [dashboard integration](docs/09_DASHBOARD_INTEGRATION.md) for startup and
first-Admin bootstrap. Rafa confirmed ORCID login via `127.0.0.1`, first-Admin
bootstrap and dashboard stock/review counts on 2026-11-18. The dashboard checkpoint
pins the matching registry commit in its requirements. Broader workflow acceptance
and release checks remain in stage 4; local testing is not a production rollout.

## Stage 4 — Verify and release

- Run the registry suite on PostgreSQL in standalone and dashboard configurations,
  including role revocation, typed approval, events, occupancy and exports.
- Verify fresh migrations/default inventory, package installation and collected
  static assets in a clean environment; run dashboard integration tests with the
  module enabled and disabled. Exercise browser workflows in both hosts.
- Document configuration, supported core revision, database setup/runtime grants,
  migration order, package pin, backups and rollback limits. Run migrations once
  per release using an appropriate setup identity, not during module registration.
- Agree an operational backup/restore procedure before retaining real records.
  A reusable cross-installation restore/import mechanism remains separately scoped.

**Done when:** both running modes are reproducible, contract checks pass, and the
dashboard deployment can be reviewed and rolled out with a documented recovery path.

## Work intentionally deferred

Researcher access; cross-installation user/data transfer; full backup import
tooling; Excel import UX/compatibility; stronger reauthentication if later needed;
off-site return and repeated-screening workflows; unrelated bulk-edit features.

Scientific invariants remain in `docs/02_SCHEMA_V0_1.md`; storage rules remain in
`docs/08_STORAGE_LOCATIONS.md`. This plan replaces the obsolete prototype roadmap
previously held in `docs/04_DEVELOPMENT_ROADMAP.md`. Older dated implementation
notes describe existing behavior; the role/approval decisions above define the
next changes, not features already implemented.
