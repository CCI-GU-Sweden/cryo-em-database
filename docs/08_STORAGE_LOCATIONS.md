# Storage locations and inventory rules

The [README](../README.md#use-the-registry) walks through storage in the app. This document describes the rules behind it.

## Locations and capacity

A grid's recorded location follows **dewar → cane → puck → gridbox → slot**. A fresh database includes Dewar 1, Cane 1, eight named pucks and four gridbox types. The current puck registration form adds pucks to Cane 1 in Dewar 1.

- A puck holds up to 12 gridboxes, including empty boxes. Puck names or colours are unique within the cane, ignoring case.
- A gridbox represents one physical box. Its name is unique across the registry, ignoring case.
- A gridbox type defines the slot layout and which slots accept clipped or unclipped grids. Mixed boxes label slots C1–C4 and U1–U4.
- A slot holds at most one grid. Each grid has at most one current slot.
- At CCI, boxes containing grids belong in a puck in the dewar. An empty box can be kept in stock. A puck can move to stock only when none of its boxes contains grids. Its empty boxes stay attached.
- Empty pucks start in stock. Staff can explicitly record an empty puck in the dewar. Placement marks a puck containing grids as in the dewar, and removing its last grid can return it to stock.

## Placement and clipping

**Store / move** lets staff select a compatible box and a free slot, or register a new box inline. For a box in stock, staff must also select a puck with room. The service assigns the box to that puck and places the grid in one transaction. The service rechecks permissions, record versions, clipping compatibility and capacity before saving.

Staff can record clipping at placement or update it in the grid's preparation form. If the updated clipping state conflicts with the current slot, the registry frees the slot and marks the location **Unknown — needs review**. The previous location stays in the physical history. Save pending preparation changes before using the separate storage controls.

## Status and transfer

- **In storage** applies after placing a grid in a CCI slot. A grid without a recorded location needs review.
- **Screened and recovered** keeps the grid in its current slot. Both screening outcomes require recorded storage.
- **Screened and discarded** and **Discarded** release the slot. Staff can record a reason. The app shows the recorded discard location.
- **Transferred to [destination]** follows a box transfer. The action records the destination, actual transfer time, actor and previous puck. It frees the puck space and updates custody for every grid in the box. Staff can inspect transferred records separately.

Only empty boxes can be discarded. Discarded boxes remain inspectable. A mistaken grid registration can be archived through the separate deletion workflow once it no longer occupies a slot.

## History and corrections

Physical actions record immutable events separately from edit audit records. Box actions that change grid custody also record events for the affected grids. The app displays timestamps to the minute and retains full precision in storage.

Authorized staff can correct eligible latest box movements, transfers, discards or grid status changes by entering a reason and typing `approve`. The original event remains in history. A correction can restore a location only when current inventory constraints allow it, including puck capacity, slot availability and clipping compatibility. Physical returns after transfer and repeated screening are outside the current workflow.

Storage filters combine with preparation filters. Excel export includes current storage, grid status and a readable event summary. See the [Excel format](05_EXCEL_EXPORT.md) for its scope.
