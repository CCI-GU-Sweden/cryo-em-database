# CCI Cryo-EM Grid Registry — Codex Handoff

**Specification baseline:** v0.1  
**Prepared:** 2026-11-02  
**Status:** Local scaffold implemented on a feature branch; grid registration is the next slice

This directory contains a **repo-ready handoff** for building a small web application to register, edit, locate, and track cryo-electron microscopy (cryo-EM) grids prepared at the Centre for Cellular Imaging (CCI). The initial user population is CCI staff; the data model should support tightly restricted external accounts later.

## Local development environment

Use Conda for this prototype. The human-maintained dependency list is
[`environment.yml`](environment.yml). From the repository root:

```bash
conda env create --file environment.yml --prefix ./.conda
conda activate ./.conda
```

The environment lives in the ignored `.conda/` directory. It includes Python 3.13,
Django 5.2 LTS, psycopg 3, PostgreSQL 17, python-dotenv and Ruff. PostgreSQL is
included so local development can work without Docker; installing it does not
start a server. The commands below initialize a private loopback database.

After deliberately changing `environment.yml`, update the environment with:

```bash
conda env update --file environment.yml --prefix ./.conda --prune
```

Keep secrets in a private `.env` file, never in the environment YAML. Use synthetic
data while the prototype model is being evaluated.

### Run the local prototype

With the Conda environment activated, run from the repository root:

```bash
python dev.py
```

The launcher prepares configuration and the database, applies migrations, and
prompts you to create an administrator if none exists. On later runs it preserves
your settings, accounts and records, then starts the app directly.

Open **http://127.0.0.1:8000/** and sign in with your administrator account.
The first page confirms the scaffold is working; grid registration comes next.
`configure_local.py` generates private local secrets and keeps an existing `.env`
unchanged. The database helper initializes `.local/postgres/` on its first run,
then starts PostgreSQL on loopback port 5433 and creates `cci_prototype` if absent.
Changing credentials in `.env` does not change credentials inside an existing
cluster; keep those values consistent. Stop the application with Ctrl+C, then:

```bash
python dev.py stop
```

The helper retains the database on stop. Use `status` to check whether it is
running. This setup targets local Linux/WSL development and uses disposable
synthetic data. It is not a shared or production deployment.

For ordinary staff accounts, use `/admin/` to add a user and enable **CCI staff
member**. That flag permits registry access; Django's separate **Staff status**
flag permits entry to the administration site. The initial superuser has both
administrative and registry access. Accounts can be deactivated rather than
deleted. Future owner grants will control record editing.

If Docker is preferred, use `docker compose up -d db` **instead of** the database
helper, after running `python scripts/configure_local.py`. Use the individual Django
commands (`migrate`, `createsuperuser`, `runserver`, `test`) with Docker; `dev.py`
manages the Conda PostgreSQL server. The same connection settings apply.
Docker is optional and its configuration has not been executed in this WSL setup.

### Verify changes

Run all checks with:

```bash
python dev.py check
```

This prepares the local database if necessary, checks Django configuration and
missing migrations, runs the tests, and checks linting and formatting. It stops
at the first failed command. PostgreSQL stays running until `python dev.py stop`.

Django creates and removes a separate test database. The local database role
needs permission to create it; the prototype cluster's initial role has this.
Tests cover login, logout, CSRF, unsafe redirects, deactivated accounts, and
registry/admin access boundaries. The custom user model is established in the
initial migration so later authentication changes retain stable user IDs.

For an exact recreation of the tested **Linux x86-64** environment, use
`conda create --prefix ./.conda --file environment-linux-64.lock` instead of the
YAML create command. Other platforms should resolve `environment.yml`. After an
intentional dependency update, regenerate the platform snapshot:

```bash
conda list --prefix ./.conda --explicit --md5 > environment-linux-64.lock
```

## Start here

1. [`docs/01_PRODUCT_BRIEF.md`](docs/01_PRODUCT_BRIEF.md) — problem, operational workflow, goals, scope, and design principles.
2. [`docs/02_SCHEMA_V0_1.md`](docs/02_SCHEMA_V0_1.md) — agreed entities, field-level structure, invariants, lifecycle, and relationships.
3. [`docs/03_ARCHITECTURE_AND_SECURITY.md`](docs/03_ARCHITECTURE_AND_SECURITY.md) — candidate Django implementation, forms and bulk editing, identity, authorization, and audit requirements.
4. [`docs/04_DEVELOPMENT_ROADMAP.md`](docs/04_DEVELOPMENT_ROADMAP.md) — vertical slices, milestones, dependencies, and delivery criteria.
5. [`docs/05_EXCEL_IMPORT_SPEC.md`](docs/05_EXCEL_IMPORT_SPEC.md) — exact workbook column map, data-quality issues, and import behavior.
6. [`docs/06_ACCEPTANCE_TESTS.md`](docs/06_ACCEPTANCE_TESTS.md) — scenarios and tests Codex should implement.
7. [`docs/07_OPEN_DECISIONS.md`](docs/07_OPEN_DECISIONS.md) — bounded unresolved details; do not silently invent a scientific convention.
8. [`AGENTS.md`](AGENTS.md) — instructions for Codex or another repository-based coding assistant.

## Agreed scientific/operational model

A **preparation session** is a real laboratory session, belongs to **exactly one sample owner**, and creates multiple individual **grids** with a saved snapshot of the shared preparation settings. At creation, each grid gets its own independent copy of the preparation fields. The user may subsequently modify individual grids, assign their storage locations, clip/move/image/discard them, or ship them outside CCI. The physical history is append-only. **Grid number is a permanent, globally unique natural identifier.**

The initial Excel example uses `CCI-00001` etc. The new application should also support owner-based identifiers such as `kegu-1234`, without rewriting historical IDs.

## Important distinction

- **Already agreed:** schema concepts, one owner per preparation session, copied defaults, optional experiment reference, staff-only initial access, complete history, both forms and table editing.
- **Prototype baseline:** Django + PostgreSQL, local Django accounts, server-rendered forms and a plain table. Advanced table tooling and shared hosting follow workflow review.
- **Unresolved:** some values/units in the source Excel, exact prefixes/sequences, whether staff may edit every owner's records, and detailed storage hierarchy rules. See `docs/07_OPEN_DECISIONS.md`.

## Source workbook

The uploaded source workbook was inspected for this handoff: **`Cryo-EM_grids_example.xlsx`**, worksheet `Sheet1`, used range `A1:AC724`, headers in row 3, eight populated grid records in rows 4–11, and prefilled identifiers below. The workbook is **not duplicated in this documentation package**. Place a privately held copy under `data/raw/` for actual import tests; never commit identifying laboratory data to a public repository.

## Recommended first Codex task

> Read AGENTS.md and docs/01–07. Implement roadmap Phases 0–1: a local Django/PostgreSQL prototype with login, owner administration, session registration, generated-grid table and individual grid editing. Preserve independent preparation values, immutable session defaults, stable identities and audit history. Use synthetic data and the documented DEMO identifier fallback until D01 is resolved. Include model, service, permission and form tests. Demonstrate registration before adding physical storage and advanced table interactions.

## Working rule

Keep documentation updated when an implementation decision is approved. Schema changes should get a migration, a test, and a short explanation of impact on Excel import and future knowledge-base extension.
