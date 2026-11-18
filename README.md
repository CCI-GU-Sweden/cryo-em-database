# CCI Cryo-EM Grid Registry

The Centre for Cellular Imaging (CCI) Cryo-EM Grid Registry tracks grid preparation, physical storage, screening outcomes and transfers between laboratories. Staff can search the registry and export preparation and storage data to Excel.

Run it locally with Django accounts or deploy it as a module in the CCI Django Dashboard with ORCID sign-in. Both modes use Python 3.12, Django 5.2 and PostgreSQL 17.

## Install and run locally

From the repository root, use Conda to install the application dependencies and local PostgreSQL tools:

```bash
conda env create --file environment.yml --prefix ./.conda
conda activate ./.conda
python dev.py
```

### First startup

1. After you run `python dev.py`, the launcher generates local secrets in a private `.env`, starts PostgreSQL and applies the database migrations. You do not need to enter database credentials.
2. When the terminal asks you to create your first local administrator, enter a username, optionally enter an email address, and type the same password twice. Press Enter at the email prompt to leave it blank. The terminal does not show characters as you type the password.

   The prompts look like this, with the database setup output omitted:

   ```text
   Create your first local administrator account.
   Username: grid-admin
   Email address:
   Password:
   Password (again):
   Superuser created successfully.

   Open http://127.0.0.1:8000/ in your browser.
   ```

3. Keep the terminal running and open [127.0.0.1:8000](http://127.0.0.1:8000/). Sign in with the username and password you just chose. That account already has the **Admin** role. Create additional users in Django admin at `/admin/` and assign the **Staff** role to users who need registry access.

On later starts, the launcher reuses your database and skips the administrator prompt if an active local superuser already exists.

Stop the web app with Ctrl+C, then run `python dev.py stop` to stop PostgreSQL. Run `python dev.py check` for the standalone test suite and development checks.

If you have a database from before the beta migration baseline, stop the app and choose a new `POSTGRES_DB` in `.env` before starting again. This creates a fresh database and preserves the old one.

## Deploy through the dashboard with ORCID

1. Install `cci-grids` into the dashboard's Python environment from a pinned registry commit or a built wheel. Build a wheel from this checkout with `python -m pip wheel --no-deps --wheel-dir dist .`.
2. Register the module using the dashboard contract and set `DASHBOARD_GRIDS_ENABLED=1` in a dashboard build that supports the registry. Configure the host to use PostgreSQL and set up ORCID with a callback URL matching the deployed dashboard address.
3. Run `python manage.py migrate` and `python manage.py collectstatic --noinput` from the configured dashboard environment, then start or restart the dashboard.
4. Sign in through ORCID. A dashboard administrator grants **Staff** or **Admin** access. Once approved, open **Grid Registry** from the dashboard home page.

See the [dashboard integration guide](docs/09_DASHBOARD_INTEGRATION.md) for the registration settings, first-admin bootstrap and local ORCID testing. Keep secrets in the host environment or private `.env` files.

### Use ORCID with your own Django host

The CCI Django Dashboard is the tested ORCID setup. A different Django host can install `cci-grids` as a reusable app, but it must provide its own ORCID sign-in, account provisioning and approval, and a user model with compatible **Staff** and **Admin** roles. It must also configure PostgreSQL and mount the registry URLs. The standalone launcher uses local Django accounts and has no ORCID switch. For a local ORCID trial, the documented setup runs the CCI Django Dashboard with only the registry enabled.

## Use the registry

1. **Start a preparation session.** Choose **New preparation session** and select an existing sample owner. If the owner is new, register them from the session form. A sample owner identifies the source of the grids and is separate from a login account.
2. **Create grids.** Enter the shared preparation conditions and the number of grids. The registry assigns grid IDs and keeps a snapshot of the session defaults. Open individual grids to edit their preparation details.
3. **Record storage.** In the session's grid table, choose **Store / move**, then select a compatible gridbox and a free slot. You can register a box inline. Choose a puck when placing a grid into a box that is still in stock. Grids without a recorded location are marked **Unknown — needs review**.
4. **Record screening or disposal.** Open a grid and choose the appropriate outcome. Screening and recovery keeps the grid in its recorded slot. Discarding releases the slot and retains the history. When a sensitive action asks for confirmation, type `approve`.
5. **Transfer to another laboratory.** Open the gridbox and choose **Transfer to another laboratory** under **Manage box**. Record the destination and transfer time. The transfer applies to every grid in the box.
6. **Find and export records.** Use **Grids** to search and filter, or browse **Sessions**, **Owners**, **Gridboxes** and **Pucks**. Excel export includes the matching grid data and storage information. Use database backups to preserve the complete history.

Active Staff and Admin users can work across the registry. The application records the operator and keeps an audit history. Deleting a mistaken registration archives it separately from physical disposal.

### Grids View

Open **Grids** from the main navigation. The table has one row per grid, with columns for its ID, sample owner, preparation details, storage location and other fields. Use **Previous** and **Next** below the table to browse pages. Separate views for transferred, discarded and deleted grids are linked above the table.

- **Storage** shows the recorded location. Click the puck name or gridbox name to open its inventory page. The slot label tells you where the grid sits inside the box. A grid without a recorded location shows **Unknown — needs review**.
- **Action** contains **View / edit**, which opens the detailed view for that grid. You can also click its **Grid ID**. The detail page brings together preparation details, storage actions, status actions and history.

To narrow the table, search by grid ID, sample, owner or experiment. Open **Sample and preparation filters** to filter by a property such as sample description or blot time. Open **Storage filters** to narrow by puck, box, slot or clipping state. Use **Add preparation filter** or **Add storage filter** to combine criteria. All criteria must match, and the endpoints of numeric ranges are included. Click **Apply search and filters** to see the results or **Clear filters** to start over.

Open **Choose columns** above the table and tick the fields you want to see. **Show all** displays every column, and **Reset to defaults** restores the initial selection. Your browser remembers the selection for your account. **Export filtered grids to Excel** includes every matching grid across all pages, regardless of which columns are visible.

### Sessions View

Open **Sessions** from the main navigation to browse preparation sessions, with the most recently registered sessions first. Each row shows the sample owner, preparation date, operator, grid count, and experiment and project references.

Search by session number, owner, operator, experiment or project. You can also select a sample owner and set a preparation date range. Click **Search sessions** to apply the filters or **Clear filters** to reset them. **Export grids for matching sessions** downloads the active grids from every matching session across all pages.

Click a session name in the **Session** column to open its detail page and see the grids prepared in that session. From there, you can open an individual grid, use **Store / move** to record its location, or follow **View archive** if the session has deleted grid records.

### Owners View

A **sample owner** is the person or group associated with a sample. For example, a CCI staff member can prepare grids for a visiting research group and select that group as the owner. The registry records the signed-in staff member separately as the preparation operator. Registering a sample owner creates a sample record only. The owner can have no account in the app.

Open **Owners** to search by name, code or affiliation. Each row shows the owner's code, affiliation and active or inactive status. Click **Sessions** to see that owner's preparation sessions or **New session** to start one with that owner preselected. Only active owners can be selected for a new session. Administrators can update an existing record through **Manage owner**. **Export grids for matching owners** downloads active grids for all owners matching the search.

To add a person or group, choose **Register a sample owner**, enter their name and click **Create unique code**. The registry gives the owner a unique four-character **code**, which becomes the prefix for their grid IDs. For example, **Alex Rivera** gives `alri` from the first two letters of the first and last words. A single-word name uses its first four letters, with `x` padding for short names. If a code is already taken, the registry tries numbered variants such as `ari1` and `ar10`. Review the code, add any affiliation or notes, and save. The registry checks uniqueness again on save and keeps the assigned code even if the owner's name changes.

### Gridboxes View

Open **Gridboxes** to find boxes by name or filter by state, such as **In stock**, **In a puck** or **Transferred**. Each row shows one physical box, its type, its location or state, and how many slots are occupied out of the total.

A **box type** is a reusable template. It defines the layout, the number of slots and which slots accept clipped or unclipped grids. To record an individual physical box, give it a unique name and select its type under **Register a physical gridbox**. Multiple physical boxes can use the same type.

Click a box name to see its layout, slot list and action history. Free slots show **Empty**. Occupied slots show a grid ID that links to the grid's detail page.

At CCI, a box containing grids must be assigned to a **puck–dewar combination**. If you place a grid into a box that is in stock, the registry asks you to select a puck. The selected puck determines the dewar. Empty boxes can be kept in stock.

### Pucks View

Open **Pucks** to see the puck inventory. A fresh installation comes with a predefined set of pucks under **Cane 1** in **Dewar 1**. These defaults can be adapted for another facility through the storage setup. In the registry, use **Register new puck** to add a physical puck. Enter a unique name or colour, type `approve` to confirm, and click **Register puck**. New pucks start **In stock**.

Each row shows the puck's name, its **Occupied box spaces** out of 12, the total number of grids in those boxes, and whether the puck is **In dewar** or **In stock**. For example, **3/12** means three gridboxes are assigned to the puck and nine box spaces are available. An empty gridbox still takes up a box space.

Click a puck name to see its gridboxes, their slot occupancy and the puck's movement history. Use **Move puck** to record its location. A puck containing grids must stay in the dewar. Before moving it to stock, remove the grids from its boxes. Empty boxes can stay attached to the puck.

### Single Grid View

Open an individual grid by clicking its **Grid ID** or **View / edit** in the Grids table or a session's grid table. You can also click the grid ID next to an occupied slot on a gridbox's detail page. The grid page shows the sample owner and links back to the preparation session.

- **Sample preparation.** Expand the relevant sections to edit the preparation details, then click **Save this grid**. Changes apply to this grid only and preserve the original session settings.
- **Clipping.** Expand **Clipping**, update whether the grid is clipped, and click **Save this grid**. If the new clipping state is incompatible with the recorded slot, the registry releases the slot and flags the location for review.
- **Location and storage actions.** Check the current location, then select a compatible gridbox and a free slot to store or move the grid. Click **Confirm placement** to record the move. This section also shows the grid's physical history.
- **Grid status.** Check the current status or use **Record status** to record screening and recovery, screening and discard, or discard without screening. If a correction is available, **Correct last status change** records the correction and preserves the original entry.

## Reference

- [Schema and preparation fields](docs/02_SCHEMA_V1_0.md)
- [Storage locations and inventory rules](docs/08_STORAGE_LOCATIONS.md)
- [Excel export](docs/05_EXCEL_EXPORT.md)

## License

Released under the [MIT License](LICENSE).
