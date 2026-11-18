# Database schema — V1.0

The registry uses PostgreSQL. The [Django models](../cci_grids/models.py), [inventory models](../cci_grids/storage_models.py) and [migrations](../cci_grids/migrations/) define the schema. Registry tables use the `registry_` prefix. Account references point to the configured host user model in both standalone and dashboard deployments.

## Preparation and ownership

| Model | Stored data and relationships |
|---|---|
| `SampleOwner` | Person or group associated with samples. Stores a name, unique code, affiliation, notes and active flag. New owner codes have four characters and stay fixed after registration. |
| `PreparationSession` | One owner, optional historical operator and preparation time, experiment/project references, notes and a versioned JSON snapshot of the original preparation defaults. A unique request token prevents duplicate submissions. |
| `Grid` | One physical grid with an immutable public grid ID and original session. Stores independent preparation values, clipping state, lifecycle status, notes and an optimistic edit version. The optional source-grid relationship is reserved for a copy workflow. |
| `GridIdentifierCounter` | Tracks the next identifier per owner code. The service allocates IDs transactionally with session creation. |
| `OwnerAccessGrant` | One grant per user and owner, with a viewer, operator or editor role. Grants are reserved for future access rules. Active Staff and Admin permissions are enforced by the application. |
| `PreparationSuggestion` | Reusable previous values keyed by field name and value, with source metadata. |

Session labels are derived from the session ID, owner code and preparation date in Europe/Stockholm. A session's original defaults stay fixed when an individual grid changes. Numeric measurements use decimal fields and retain unknown values as NULL where allowed. Application validation checks units and the allowed carbon thickness fields.

## Physical inventory

| Model | Stored data and relationships |
|---|---|
| `Dewar` / `Cane` / `Puck` | Storage hierarchy. Each cane belongs to one dewar and each puck to one cane. Cane names are unique within a dewar and puck colours are unique within a cane, ignoring case for puck colours. Pucks record whether they are in the dewar. |
| `GridBoxType` | Reusable template with a unique code, display name, layout image and JSON slot layout defining capacity and clipping compatibility. |
| `GridBox` | One physical box with a case-insensitively unique name, a type, optional current puck, discard flag and optional transfer timestamp and destination. |
| `GridSlot` | Unique box, side and position combination, with an optional one-to-one reference to the grid occupying it. |

The slot association records a grid's current box and position. Its box determines custody and the puck, cane and dewar where applicable. Grid status and custody are updated by the same transaction as physical actions. Placement and custody services enforce slot compatibility and puck capacity. See [storage rules](08_STORAGE_LOCATIONS.md) for the lifecycle and default inventory.

## History and constraints

| Model | Purpose |
|---|---|
| `GridEvent` | Physical action with actor, occurrence and recording times, optional source/destination slots, optional related box action and JSON details. |
| `BoxEvent` | Box action with actor, timestamps, source/destination pucks, transfer destination and an optional reference to the action being corrected. |
| `PuckEvent` | Recorded change to the puck's dewar status, with actor and recording time. |
| `AuditEvent` | Audit record with actor, entity type and ID, operation, change payload, source and recording time. |
| `DeletedGrid` | One-to-one archive marker recording who archived a grid and when. The original grid and its history are retained. |

PostgreSQL constraints enforce unique identifiers, unique slot positions and single-grid occupancy, measurement bounds where defined, and valid box transfer/discard combinations. Database triggers protect grid identity and original session membership, make archived grids read-only, preserve the original session defaults and prevent updates or deletes to event, audit and archive records. A trigger also prevents discarding a box that still contains grids. Authorized service methods enforce the additional workflow rules and append correction records.

## Grid field reference

Run `python manage.py describe_grid_fields --update-docs` to regenerate this table. `python dev.py check` checks it against the model. Application defaults and model bounds are listed separately from PostgreSQL constraints.

<!-- generated-grid-fields:start -->
| Field | PostgreSQL type | NULL allowed | Empty text allowed | Application default | Model bounds |
|---|---|---|---|---|---|
| `id` | `bigint` | No | No | Generated ID | >= -9223372036854775808, <= 9223372036854775807 |
| `is_clipped` | `boolean` | No | No | False | — |
| `status` | `varchar(24)` | No | No | unknown | — |
| `grid_number` | `varchar(80)` | No | No | — | — |
| `session_id` | `bigint` | No | No | — | — |
| `copied_from_grid_id` | `bigint` | Yes | No | — | — |
| `sample_description` | `text` | No | Yes | — | — |
| `sample_concentration_value` | `numeric(12, 2)` | Yes | No | — | >= 0 |
| `sample_concentration_unit` | `varchar(40)` | No | Yes | — | — |
| `buffer_description` | `text` | No | Yes | — | — |
| `grid_type` | `varchar(200)` | No | Yes | — | — |
| `grid_box_number` | `varchar(100)` | No | Yes | — | — |
| `carbon_description` | `varchar(200)` | No | Yes | — | — |
| `carbon_thickness_nm` | `numeric(12, 2)` | Yes | No | — | >= 0 |
| `carbon_thickness_layers` | `integer` | Yes | No | — | >= 0, <= 2147483647 |
| `glow_device` | `varchar(200)` | No | Yes | — | — |
| `glow_atmosphere` | `varchar(100)` | No | Yes | — | — |
| `glow_polarity` | `varchar(100)` | No | Yes | — | — |
| `glow_current_ma` | `numeric(12, 2)` | Yes | No | — | — |
| `glow_duration_s` | `numeric(12, 2)` | Yes | No | — | >= 0 |
| `freezing_device` | `varchar(200)` | No | Yes | — | — |
| `sample_volume_ul` | `numeric(12, 2)` | Yes | No | — | >= 0 |
| `temperature_c` | `numeric(12, 2)` | Yes | No | — | — |
| `humidity_percent` | `numeric(7, 2)` | Yes | No | — | >= 0, <= 100 |
| `blot_time_s` | `numeric(12, 2)` | Yes | No | — | >= 0 |
| `hold_time_s` | `numeric(12, 2)` | Yes | No | — | >= 0 |
| `drain_time_s` | `numeric(12, 2)` | Yes | No | — | >= 0 |
| `blot_force` | `numeric(12, 2)` | Yes | No | — | — |
| `multiple_blot` | `integer` | No | No | 0 | >= 0, <= 2147483647 |
| `notes` | `text` | No | Yes | — | — |
| `version` | `integer` | No | No | 1 | >= 0, <= 2147483647 |
| `created_at` | `timestamp with time zone` | No | No | Time of creation | — |
| `updated_at` | `timestamp with time zone` | No | No | Time of save | — |
<!-- generated-grid-fields:end -->
