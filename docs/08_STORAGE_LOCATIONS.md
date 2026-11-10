# CCI Cryo-EM Grid Registry — Storage Locations

**Document:** `08_STORAGE_LOCATIONS.md`\
**Schema context:** CCI Cryo-EM Grid Registry v0.1\
**Date:** 2026-11-10\
**Status:** Agreed requirements for the initial implementation

## 1. Purpose

This document defines how physical storage locations for cryo-EM grids should be represented in the CCI Cryo-EM Grid Registry.

The application must represent the physical hierarchy used by CCI, validate that a selected grid position is valid for its gridbox type, and retain the storage history of each grid when it is moved, clipped, shipped, removed, or discarded.

The current setup has **one dewar and one cane**. The initial UI enforces
`Dewar 1` and `Cane 1`; users cannot select or enter other values. The data
model keeps them as distinct levels so additional dewars and canes can be
configured later without redesigning the grid storage model.

## 2. Physical storage hierarchy

The hierarchy is:

```text
Dewar
└── Cane
    └── Puck
        └── Gridbox
            └── Gridslot
```

Each level identifies a progressively smaller physical location.

| Level | Initial value or input | Notes |
|---|---|---|
| Dewar | Fixed: `Dewar 1` | The initial UI enforces the only configured choice. |
| Cane | Fixed: `Cane 1` | The initial UI enforces the only configured choice. |
| Puck | Select a colour | The puck is identified by its colour. |
| Gridbox type | Select a predefined type | Determines the available positions and, where relevant, the two-sided layout. |
| Gridbox name | Free-text input | Unique identifier for the physical gridbox across the registry. |
| Gridslot | Select/enter a valid position | Must be valid for the selected gridbox type. |

The user interface should present the hierarchy as a sequence of related selections:

**Dewar → Cane → Puck → Gridbox type → Gridbox name → Gridslot**

The initial interface displays and enforces the sole dewar and cane. They should
not be hard-coded into the underlying storage-event logic in a way that prevents
additional dewars or canes from being configured in a future release.

## 3. Puck colours

The initial supported puck colours are:

- Black
- Dark blue
- Gold
- Green
- Light blue
- Purple
- Red
- Silver

Store the colour as a controlled value rather than unrestricted free text. The interface may display friendly labels while the database uses stable internal codes, for example `dark_blue` and `light_blue`.
Leave room for a mechanism to add colours later; adding a colour is not part of
ordinary free-text storage entry. The management workflow remains to be decided.

A puck should be uniquely identifiable within its parent cane. Since colour is the current identifying attribute, the initial implementation should prevent duplicate puck-colour entries within the same cane unless the laboratory later establishes an additional identifier or naming convention.

A puck holds at most **12 physical gridboxes**. Do not record which of the
puck's 12 positions holds a particular box: only the box's parent puck is
tracked. A two-sided gridbox is one physical box and counts once toward the
limit. Creating or moving a box into a puck must enforce the capacity safely;
the handling of retired boxes and physical box moves needs to be defined before
implementation so the count reflects boxes physically present.

## 4. Gridbox types and capacity

The gridbox type determines its physical arrangement and valid grid positions.
Types are a controlled selection. New types will be added rarely and must have a
name, an SVG image and a defined number of positions. Their definition must also
specify the valid slot identifiers, any sides and clipped/unclipped compatibility:
a capacity alone cannot describe the existing two-sided layout. The process for
adding a type is future work; this does not require a v0.1 type-management screen.

| Gridbox type | Capacity | Position model |
|---|---:|---|
| `Unclipped (4)` | 4 | One side with positions 1–4; accepts unclipped grids. |
| `Clipped (4)` | 4 | One side with positions 1–4; accepts clipped grids. |
| `Clipped + unclipped (4 + 4)` | 8 | Two sides: clipped positions 1–4 and unclipped positions 1–4. |
| `Clipped (12)` | 12 | One side with positions 1–12; accepts clipped grids. |

### 4.1 Two-sided gridbox

`Clipped + unclipped (4 + 4)` represents **one physical gridbox with two sides**, not two separate gridboxes.

For this type, a position must be identified using both:

- `side`: `clipped` or `unclipped`
- `position`: integer from 1 to 4

For the other gridbox types, the position is identified by its integer slot number. The side can be treated as implicit from the gridbox type, or stored as a nullable field where a consistent schema is preferred.

### 4.2 Validation rules

The application must validate the gridbox layout when assigning a grid to a position:

- `Unclipped (4)`: positions 1–4 only; the grid must be unclipped.
- `Clipped (4)`: positions 1–4 only; the grid must be clipped.
- `Clipped + unclipped (4 + 4)`: side is required; positions 1–4 are valid on each side; the grid's clipping state must match the selected side.
- `Clipped (12)`: positions 1–12 only; the grid must be clipped.
- A physical position must not be occupied by more than one grid at the same time.
- A grid must not have more than one current storage position at a time.
- Slot choices are determined by the selected type, including side where required.

The validation should be enforced by the application/backend, not only by disabling choices in the user interface.

## 5. Gridbox identity

Each gridbox has:

- A `gridbox_type`, selected from the controlled list above.
- A `gridbox_name`, entered as free text.

The gridbox name is the physical box's free-text unique ID across the registry;
the puck is its place in the hierarchy, not part of its identity. It should not be
confused with the gridbox type: several physical gridboxes may share the same type.
Staff can select a previously used name when assigning storage. A reused name
must resolve to the same physical box, not create a duplicate.

The application must prevent duplicate gridbox names across all pucks. Exact
normalization rules for names should be decided before enforcing uniqueness.

### 5.1 Reusable physical gridboxes and inventory

A registered gridbox represents a long-lived physical item, not a container
created for a particular grid, preparation session or project. The same box can
hold grids from different projects over time, and a vacated gridslot can be
reused for another grid. Reuse must preserve the history of previous occupants.

Staff need a gridbox management view to inspect registered boxes, their type and
current contents, and whether each box is in stock, currently in a puck, or
discarded (for example, because it is broken). A box can be in a puck while
having no grids in its slots: being physically placed in a puck and containing
grids are separate facts. An empty slot becomes available for a new grid only
when the previous grid no longer occupies it.

Track whether a box is physically in a puck separately from whether any of its
grid slots are occupied. A box held in stock is not counted against a puck's
12-box capacity; a box physically in a puck counts once even if all of its grid
slots are empty. Keep discarded boxes and their grid histories available for
inspection rather than silently deleting them.

The specific stock, placement, removal, discard and correction workflows,
including when moving or discarding a box containing grids is allowed and how
box-location history is recorded, require agreement before implementation.
No project relationship or box state should be inferred from its current or
previous grid occupants.

## 6. Recommended data representation

The storage hierarchy should be represented as structured data, not as one concatenated location string.

A practical initial relational model is:

### `Dewar`

| Field | Type | Notes |
|---|---|---|
| `id` | Primary key | Internal identifier. |
| `name` | Text, unique | Initially `Dewar 1`. |
| `is_active` | Boolean | Allows future decommissioning without deleting history. |

### `Cane`

| Field | Type | Notes |
|---|---|---|
| `id` | Primary key | Internal identifier. |
| `dewar_id` | Foreign key | Parent dewar. |
| `name` | Text | Initially `Cane 1`. |
| `is_active` | Boolean | Allows future decommissioning without deleting history. |

### `Puck`

| Field | Type | Notes |
|---|---|---|
| `id` | Primary key | Internal identifier. |
| `cane_id` | Foreign key | Parent cane. |
| `color` | Controlled value | One of the eight supported colours. |
| `is_active` | Boolean | Allows a puck to be retired without deleting history. |

At most 12 physical gridboxes may be present in a puck; no position within the
puck is stored for an individual gridbox.

### `Gridbox`

| Field | Type | Notes |
|---|---|---|
| `id` | Primary key | Internal identifier. |
| `puck_id` | Foreign key? | Current puck when placed; empty while in stock or discarded, subject to the eventual history design. |
| `name` | Text, unique | Free-text physical gridbox identifier across the registry. |
| `gridbox_type` | Controlled value | One of the four supported configurations. |
| `is_active` | Boolean | Allows a gridbox to be retired without deleting history. |

The table is a conceptual starting point: stock, placement and discard require
an explicit inventory representation; `is_active` alone does not capture them.
In particular, a box in stock has no current puck, and an empty box can still
occupy space in a puck. The exact fields and transitions remain to be designed.

### Grid position

A grid position can be represented in either of two ways:

1. As a separate `GridSlot` table containing the gridbox, optional side, and position number; or
2. As structured fields on the current storage assignment/event, with validation based on gridbox type.

For v0.1, a separate `GridSlot` table is not mandatory. The implementation should choose the simpler approach that can reliably enforce valid positions and prevent simultaneous double occupancy. If a `GridSlot` table is introduced, it should represent the physical position independently of the grid currently occupying it.

Suggested position attributes:

- `gridbox_id`
- `side` (nullable; used for the two-sided gridbox)
- `position` (integer)

## 7. Relationship to grids and storage history

A grid's current storage location is composed of the hierarchy above. The application should be able to display it as a human-readable path, for example:

```text
Dewar 1 / Cane 1 / Red puck / Gridbox A / Clipped side / Slot 3
```

For a single-sided gridbox, the side component is omitted:

```text
Dewar 1 / Cane 1 / Red puck / Gridbox B / Slot 2
```

The storage location must be linked to the grid through its storage history. When a grid moves:

1. Record the previous location.
2. Record the destination location.
3. Record the date/time and the user who performed the movement.
4. Preserve the previous event and location permanently.
5. Update the grid's current-location representation within the same database transaction.

A grid that is shipped or discarded no longer occupies a CCI storage position. Its last CCI location must nevertheless remain available in its history.

Clipping is a separate physical event and clipping state, but it affects which gridbox types/sides can accept the grid. For example, an unclipped grid cannot be assigned to the clipped side of a `Clipped + unclipped (4 + 4)` gridbox.

## 8. User-interface requirements

The storage form should be straightforward for CCI staff:

1. Dewar is fixed to `Dewar 1`.
2. Cane is fixed to `Cane 1`.
3. Staff select the puck colour.
4. Staff select the gridbox type.
5. Staff enter or select the globally unique gridbox name; previous names are reusable.
6. The application presents only valid slot choices for that gridbox type and the grid's clipping state.

The interface should show the hierarchy in a readable, associated form. It may also display a compact combined location string in the grid registry table, while retaining each component as an individual database field/reference.

For batch registration, the storage fields should initially be empty. Storage is assigned when the physical grid is placed in a known location. The application may support assigning locations to several grids in one operation, provided each selected position is validated and unique.

## 9. Initial configuration and future extension

For the initial MVP:

- Configure one dewar: `Dewar 1`.
- Configure one cane: `Cane 1`.
- Offer the eight puck colours listed above and allow for later additions.
- Limit each puck to 12 physical gridboxes, without tracking their positions within the puck.
- Support the four gridbox types listed above; later types need a name, SVG, capacity and slot layout.
- Allow free-text gridbox names that uniquely identify boxes across the registry.
- Validate grid slots and clipping compatibility.

Do not assume that one dewar and one cane will always be sufficient. They are configuration data, not permanent application constants. Future work may include:

- Multiple dewars and canes.
- Additional puck identifiers or colours.
- Additional gridbox types and capacities.
- More detailed physical inventory management.
- Bulk storage assignment and movement workflows.

Adding another dewar or cane in the future should be an administrative configuration task, not a database redesign.

## 10. Open implementation details

The following details can be resolved during implementation or with the cryo-EM staff; they do not block the initial schema:

- Whether puck colour is guaranteed to be unique within a cane in all circumstances. The initial assumption is yes.
- Whether gridbox names are handwritten labels, printed identifiers, or another naming convention.
- How additional puck colours and gridbox types are managed, including whether a lookup table or code-managed definitions are appropriate.
- How gridbox names are normalized for unique matching, including case and whitespace.
- Whether grids are placed directly into their final puck/gridbox/slot during initial storage or whether intermediate unassigned storage states need additional handling.
- How box movement and retirement affect physical puck occupancy and its history.
- The inventory screen and box state transitions, including rules for boxes
  that still contain grids when someone attempts to move or discard them.

Until these points are confirmed, the implementation should use the values and validation rules in this document and avoid inventing additional storage levels.

---

## Summary of agreed requirements

- The storage hierarchy is **Dewar → Cane → Puck → Gridbox → Gridslot**.
- CCI currently has one dewar (`Dewar 1`) and one cane (`Cane 1`); the UI enforces both in v0.1.
- Puck colour is selected from: black, dark blue, gold, green, light blue, purple, red, silver.
- Each puck holds at most 12 gridboxes; individual box positions within a puck are not tracked.
- Gridbox name is a free-text unique ID across the registry; previously used names can be selected.
- Physical gridboxes and slots are reusable across grids and projects. Manage
  boxes in stock, in a puck, or discarded, separately from slot occupancy.
- Gridbox type controls capacity and slot validation; a new type needs a name, SVG, capacity and layout.
- `Clipped + unclipped (4 + 4)` is one box with two sides, each containing positions 1–4.
- Clipping state is distinct from storage location and overall grid availability.
- Storage movements are historical events; previous locations must not be overwritten.
- The model must support additional dewars and canes through configuration in a future version.
