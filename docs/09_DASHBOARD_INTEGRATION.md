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

Add the following opt-in configuration to the dashboard settings, using its
existing module registration mechanism:

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
run `python manage.py migrate` once before starting the enabled deployment.
Runtime needs normal table/sequence access, not permission to remove protections.

## Local integrated trial

The agreed trial starts with a new PostgreSQL database, no grids or users, and
only the registry enabled. It does not reset the standalone registry database or
the dashboard's previous SQLite database. The standalone reset command is
intentionally unavailable in the dashboard.

For this checkout, private connection settings are stored in the ignored
`.local/dashboard.env`. Load those settings in the dashboard terminal; retain or
supply the existing `ORCID_CLIENT_ID` and `ORCID_CLIENT_SECRET` privately. The
configuration selects production ORCID, as in the earlier dashboard trial.

```bash
# Registry terminal: keep its private PostgreSQL server running.
python scripts/local_database.py start

# Dashboard terminal: activate the dashboard environment first.
set -a
source /home/xcamra/projects/cryo-em-database/.local/dashboard.env
set +a
read -rsp 'ORCID client secret: ' ORCID_CLIENT_SECRET
export ORCID_CLIENT_SECRET
echo
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Stop any other web server using port 8000 first. Open `http://127.0.0.1:8000/`;
the user confirmed this address works with the current ORCID client (2026-11-18).
Its callback is `http://127.0.0.1:8000/accounts/orcid/login/callback/`.
Using `localhost` instead produces an ORCID redirect-URI mismatch for this client.
Use the same hostname and port as the registered ORCID callback. The private trial
configuration disables uploads, OMERO and tickets. Their packages/data sources
are otherwise unchanged.

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
cd /home/xcamra/projects/cryo-em-database
../Dashboard-django/.conda/bin/python scripts/check_dashboard_integration.py \
    dist/cci_grids-0.1.0-py3-none-any.whl --dashboard ../Dashboard-django
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
