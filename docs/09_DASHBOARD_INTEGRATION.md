# Dashboard integration

The registry is an installed Django module in the dashboard process. It owns its
`registry_*` tables, migrations, scientific rules and history. The dashboard owns
accounts, ORCID authentication, account approval, sessions and deployment settings.
There is no user-copy operation: registry foreign keys reference the dashboard's
configured `AUTH_USER_MODEL` directly. Sample owners remain independent records.

This integration targets dashboard contract version 1 at core revision
`855a4d4fdb2561395253d2ab97d7c1cfc1219770`. Standalone development continues to use
`python dev.py` and the standalone accounts app. Do not install the standalone
`config` or `accounts` packages into the dashboard.

## Host registration

Install a built registry wheel in the dashboard's Python environment. For a
reproducible deployment, pin the reviewed registry release or full Git commit in
the dashboard requirements and rebuild its image. A locally installed wheel is a
development test, not a published release pin. Do not add a sibling checkout to
production `PYTHONPATH`.

If your dashboard checkout does not already register the registry, add the
following opt-in configuration to its settings:

```python
DASHBOARD_GRIDS_ENABLED = os.environ.get("DASHBOARD_GRIDS_ENABLED", "0") == "1"
CCI_GRIDS_DASHBOARD = DASHBOARD_GRIDS_ENABLED
if DASHBOARD_GRIDS_ENABLED:
    INSTALLED_APPS.append("cci_grids.apps.RegistryConfig")
    DASHBOARD_MODULES.append("cci_grids.dashboard_module.module")
```

The descriptor uses `cci_grids.dashboard_urls`, which mounts `/registry/` once.
Its card reports **Grids stored at CCI**: grids in a recorded slot of a
non-discarded box at CCI, with status In storage or Screened and recovered.
Unlocated, transferred, discarded and deleted grids are excluded.
The second count, **Unknown location — needs review**, includes current grids
without a recorded slot. Transferred, discarded and deleted grids are excluded
from this review count; lack of a slot after disposal is expected.
Do not include it again in the dashboard's root URL configuration. Enabling the
module registers its routes and overview card; it never runs migrations or
modifies accounts. Disabling the module and restarting removes those routes and
card, preserving its tables.

Use PostgreSQL 17. The registry migrations include immutable-history triggers and
storage invariants, so SQLite cannot host this module. Each app owns separate
tables in the same configured PostgreSQL database. Use a setup identity allowed
to create the registry tables, sequences, constraints and trigger functions, then
run `python manage.py migrate` with `DASHBOARD_GRIDS_ENABLED=1`. Run
`python manage.py collectstatic --noinput` before starting the deployment.
Runtime needs normal table/sequence access, not permission to remove protections.

## Local integrated trial

Use a separate PostgreSQL database for the dashboard trial. Create it before
running migrations. If you use the registry checkout's local PostgreSQL cluster,
run `POSTGRES_DB=cci_dashboard_trial python scripts/local_database.py start`
from the registry checkout with its Conda environment active.

In the dashboard environment, set `DJANGO_DEBUG=1`, supply a private
`DJANGO_SECRET_KEY`, and set `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` and
`PGPASSWORD` for the trial database. If the dashboard hosts only the registry
in this trial, set `DASHBOARD_UPLOADS_ENABLED=0`, `DASHBOARD_OMERO_ENABLED=0`
and `DASHBOARD_TICKETS_ENABLED=0`.

Supply `ORCID_CLIENT_ID` and `ORCID_CLIENT_SECRET` for your ORCID application.
The dashboard defaults to ORCID Sandbox. Set `ORCID_ENVIRONMENT=production`
when using a production client. The callback for the address below is
`http://127.0.0.1:8000/accounts/orcid/login/callback/`. Open the app using
the same host and port registered for your client. A callback registered for
`127.0.0.1` does not match `localhost`.

With these settings loaded, run from the dashboard checkout:

```bash
export DASHBOARD_GRIDS_ENABLED=1
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Sign in through ORCID to create the dashboard account in the new database. It
starts Pending. Stop the web server with Ctrl+C, then use the dashboard's own
command in that same configured terminal after a successful ORCID sign-in:

```bash
python manage.py bootstrap_admin YOUR_ORCID_ID
python manage.py runserver 127.0.0.1:8000
```

Staff and Admin may then use the registry. Researcher, Pending and disabled
accounts are denied both the overview and direct registry endpoints. Account
management stays in dashboard Administration. Sensitive registry actions require
typing `approve`; they do not request an ORCID password or a local password.

## Review before deployment

Run the installed-wheel integration harness with the dashboard's interpreter
and the `PG*` connection variables loaded. It creates uniquely named test
databases and leaves the browser trial and standalone databases unchanged:

```bash
# From the registry checkout, with the dashboard environment active.
python scripts/check_dashboard_integration.py \
    dist/cci_grids-0.1.0-py3-none-any.whl --dashboard /path/to/Dashboard-django
```

The dashboard environment needs the wheel's dependencies, including openpyxl.
The harness checks the installed module against real dashboard accounts with the
other modules disabled. It then runs the dashboard account tests in a separate
test database with their standard optional-module configuration; their test
discovery imports ticket models even when individual tests are skipped. This
does not enable those modules in the browser trial. Use
`python dev.py check` separately for the full standalone suite.

Verify fresh defaults, direct-route access controls, overview metrics, registry
navigation, administration workflows, Stockholm timestamps and packaged static
assets in the integrated host. Also run the standalone checks after changes.
Test module disable/re-enable without dropping its data. Automated integration
checks do not substitute for a real ORCID browser login.

Keep database backups for the entire host, including dashboard users and registry
history. Excel export is not a full backup. Do not restore registry rows against
unrelated user IDs. Real research data, production rollout and an operational
backup schedule require their own release review.
