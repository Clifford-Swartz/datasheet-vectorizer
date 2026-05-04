# Handoff notes

For whoever picks this up.

## Environment

- Python 3.10+ (tested on 3.14)
- Dependencies: `pdfplumber`, `openpyxl` (only for `_family_groups.py`
  reading the source XLSX). No ML libs.
- Tested on Windows 11, but the code is OS-agnostic except for path
  separators in some scripts.

## To pick up where I left off

1. **Get the PDFs back** (they're not in this repo, ~2.4 GB):

   ```bash
   python scripts/_download_datasheets.py
   ```

   This reads `family_datasheets.json` and downloads each unique URL into
   `datasheets/`. Two PDFs (AVR32DA28-32-48 and AVR32DB28-32-48) are blocked
   by Microchip's CDN with HTTP 403; nothing we can do without a different
   download path.

2. **Rebuild the part→PDF mapping**:

   ```bash
   python scripts/_build_part_to_pdf.py
   ```

3. **Vectorize**:

   ```bash
   python scripts/_vectorize_all.py    # ~10 min cold, ~2 min warm
   ```

4. **Audit + null contaminated**:

   ```bash
   python scripts/_count_wrong_pdfs_v2.py
   python scripts/_null_wrong_pdf_parts.py
   python scripts/_export_csv.py
   ```

The output files (`vectorized_all.json`, `vectorized_all.csv`,
`wrong_pdf_audit.json`) in this repo are pre-built. Re-running the above
should regenerate them identically.

## Open issues, ranked by leverage

### 1. Per-cell accuracy is 73%, not 99%
The held-out test is the metric to optimize against, not the tuning ground
truth. Specific weak fields (from
[`docs/ACCURACY.md`](ACCURACY.md)):

| Field | Held-out accuracy |
|---|---|
| TempRange_Max | 38% |
| ADC_Channels | 33% |
| Number_of_DACs | 53% |
| Program_Memory_KB | 50% |
| Auxiliary_Flash_KB | 67% |

Most of these are because:
- The table layouts vary across families and the parser doesn't recognize
  some patterns
- Family defaults are too eager (e.g. `Number_of_DACs` defaults to `0` but
  some families have DACs whose count needs to come from the table)

Fix path: extend `RAW_TO_CANONICAL` and the fuzzy fallback in
[`vectorize.py`](../datasheet_vectorizer/vectorize.py) for the missing
patterns. Use [`_inspect_tables.py`](../scripts/_inspect_tables.py) to see
what the parser sees raw before mapping.

### 2. The 231 remaining wrong-PDF parts (10.3%)
Most are irreducible — Microchip lists architecture manuals and ARM core
TRMs as "datasheets" for legacy AT32UC, XMEGA, AT91SAM9/7 parts. There is
no per-variant datasheet to find.

For the few that aren't — the failed batch 1 cluster of 5 PIC32MX5xx parts,
some PIC32CK SG/GC, a few PIC16LF — re-running discovery with the specific
part name might surface a real datasheet.

### 3. Variant-row matching is too strict
`find_variant_row()` does exact string match. Some tables list parts as
`ATSAMC20E15` but our catalog has `ATSAMC20E15A` (revision letter). The
audit script handles this with fuzzy variants, but the actual extraction
doesn't, so we'll fail to find the row even when the right datasheet is
present. Adding the same fuzzy variant logic to `find_variant_row()` would
recover several percent of cell coverage.

### 4. Family-key bucketing for new parts
If you add new parts not currently in `families.json`, you need to:
1. Add them to the catalog (the source XLSX or update
   `_family_groups.py` to read your source)
2. Re-bucket: `python scripts/_family_groups.py`
3. Run MCP rediscovery for the new families (see "Re-running discovery"
   below)

## Re-running discovery from scratch

The MCP queries that built `family_datasheets.json` ran via subagents. You
can re-run them by:

1. Calling `mcp__mchp_resources__search_microchip_product_documents` with
   `query="<part_number>"` and `limit=2`.
2. Extracting the `.pdf` URL from each document's `url` field (preferring
   `/DataSheets/` or `/DeviceDoc/` paths) or from the `**Data Sheet**:`
   markdown link in the body.

The MCP tool needs an authenticated Microchip MCP server connection. The
project setup that allows this is outside this repo.

If you don't have MCP access, you can manually populate
`family_datasheets.json` by browsing
[microchip.com](https://www.microchip.com) for each family and pasting the
PDF URL.

## Code-quality caveats

The scripts in `scripts/` are evolution-as-needed, not production-grade.
Specifically:
- Most read JSON with `encoding="utf-8-sig"` to handle BOM marks; if you
  edit a JSON file with a tool that doesn't preserve encoding, things will
  break.
- A few scripts have hardcoded paths assuming the working directory is the
  repo root.
- `_merge_part_redisc.py`, `_merge_redisc.py`, `_merge_nulls.py`, and
  `_merge_batches.py` exist for different snapshots of the discovery work
  and have overlap. The current canonical merge is `_merge_part_redisc.py`.
- The `datasheet_vectorizer` package itself is more disciplined; that's the
  part to build on.

## What I'd do next

If accuracy matters more than coverage:
- Run held-out validation on a fresh 50-part sample to get a tighter
  per-cell number
- Walk through the worst-3 fields (TempRange_Max, ADC_Channels, DACs) and
  find why they fail — usually a missing dictionary entry or a
  family-default that overrides a table extraction

If coverage matters more than accuracy:
- Wire up an LLM fallback for the 231 wrong-PDF parts and the per-variant
  table failures. Probably gets you to 95%+ at the cost of debuggability.

If you want a usable parametric DB now:
- Diff `vectorized_all.csv` against your existing parts list and only ship
  the cells where (a) the part has the right PDF and (b) the field is in
  the high-accuracy set (Pincount, IO_Pins_Max, Flash, RAM, I2C, SPI,
  USART, WDT, RTC). That's roughly 70% of the catalog × 90% accuracy = a
  trustworthy starting set.
