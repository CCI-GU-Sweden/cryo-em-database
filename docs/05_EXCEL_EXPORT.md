# Excel export

Use **Export filtered grids to Excel** in the Grids view. The export includes every matching grid across pages, including preparation fields hidden by the browser's column settings. The Sessions and Owners views also offer exports of grids from matching sessions or owners.

The workbook includes grid IDs, preparation measurements, clipping and grid status, recorded storage locations and a readable storage history. Supporting sheets include owners and preparation sessions. Use a PostgreSQL backup when you need complete records, audit history and account attribution.

## Experimental import tools

Excel import is future work. The repository contains experimental tools for importing data from registry-generated Excel exports. They are still in development, have limited validation in real workflows, and are hidden from normal navigation.

Future import of older lab workbooks needs source verification. Preserve the original values and notes, and leave uncertain fields unknown until their meaning is confirmed. In particular, do not infer humidity units, the blot force scale, batch numbers from ambiguous grid-type notes, session membership from shared experiment references, or grid lineage from free-text notes.
