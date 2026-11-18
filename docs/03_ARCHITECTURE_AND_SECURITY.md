# Architecture and security

## Application and deployment

The registry is a Django 5.2 application backed by PostgreSQL 17. It uses server-rendered forms and tables, with JavaScript for interactions such as column selection and inline storage. The [schema reference](02_SCHEMA_V1_0.md) describes its data and constraints.

| Mode | Identity and configuration |
|---|---|
| Standalone | `dev.py` starts a loopback development server and a checkout-local PostgreSQL cluster. The `config` project and `accounts` app provide local settings and Django accounts. |
| Dashboard | The dashboard installs the `cci-grids` package and enables the registry module. It supplies Django settings, PostgreSQL, ORCID sign-in, accounts, sessions and roles. The registry uses the same configured database and manages its own tables through migrations. |

The wheel contains the `cci_grids` application, migrations, templates and static assets. The app keeps the `registry` Django label and URL namespace. The [dashboard integration guide](09_DASHBOARD_INTEGRATION.md) covers registration, configuration and deployment.

## Access rules

- Active **Staff** and **Admin** users can browse the registry and work with active grids across sample owners. They can register owners and create sessions for active owners. Admins can also manage existing owners and grants.
- Pending, Researcher and disabled users are denied registry access. The application role is separate from Django's admin site access flag.
- Registry routes and domain services check permissions on the server. Mutation services reload current access so revoked privileges cannot authorize later writes. Dashboard visibility and overview metrics are also restricted to authorized users.
- User attribution references the configured user model. Sample owners are separate records. Owner grants currently neither give researchers access nor limit Staff access.
- Browsing and Excel export use the shared grid visibility boundary. Experimental import endpoints remain restricted to active Staff and Admin users.

## Writes and history

Django's CSRF protection covers browser mutations. Sensitive actions such as archiving a mistaken grid, correcting an eligible grid or box event, and registering a puck require typing `approve` after sign-in. This confirmation is a deliberate-action check. Authentication and authorization are still required.

Domain services validate scientific inputs, check record versions and use PostgreSQL transactions for operations such as session creation and grid placement. Inventory locking and database constraints prevent double assignment and enforce occupancy. See the [storage rules](08_STORAGE_LOCATIONS.md).

Physical events record handling and custody. Audit events record database changes and attribution. PostgreSQL triggers protect history, original session defaults and grid identity. Archiving records a deletion marker and makes the grid read-only. It preserves the grid ID, preparation details and history.

## Deployment and data handling

Keep credentials and research data out of Git. Use a private local `.env` or the deployment's secret configuration. The hosted dashboard should run with debug mode off, HTTPS enabled and its host and CSRF settings configured for the actual deployment. Run schema migrations through the dashboard host before enabling the module.

Limit access to the database, backups and Excel exports. A workbook export contains selected records and summaries. Database backups preserve the complete history and user attribution. Include the host's identity tables in the backup and test restoration before relying on it. The standalone reset command is for the verified checkout-local database and is unavailable in the dashboard package.
