# Architecture

## Pipeline overview

```
[PDF + part number]
       ↓
  [PDF ingest]    pdf_ingest.py — pdfplumber-based text & table extraction with disk cache
       ↓
  [Table extractor]    table_extractor.py — find Configuration Summary tables, parse the variant row
       ↓
  [Features parser]    features_parser.py — regex over the "Features" bullet list at top of every datasheet
       ↓
  [Field mapper]    vectorize.py — map raw header strings to canonical fields, apply family defaults, derive computed fields
       ↓
[JSON: { fields: {...}, sources: [(page, table_idx), ...], pdf: ... }]
```

There is no ML, no LLM, no embedding model anywhere in the pipeline. It's
deterministic regex + table parsing + a hand-written lookup dictionary.

## Stage 1: PDF ingest

[`datasheet_vectorizer/pdf_ingest.py`](../datasheet_vectorizer/pdf_ingest.py)

- Uses `pdfplumber` to extract page text (`extract_plain_text`) and tables
  (`extract_tables_pdfplumber`).
- Caches results to `.pdf_cache/` keyed by `(filename + MD5 hash + max_pages + variant)`.
  First run is slow; subsequent runs hit the cache.

## Stage 2: Table extraction

[`datasheet_vectorizer/table_extractor.py`](../datasheet_vectorizer/table_extractor.py)

This is the bulk of the engineering. Microchip's "Configuration Summary",
"Family Features", "Peripheral Overview", "Devices Included" tables list every
variant in a family with its peripheral counts. Most parametric data lives
in those tables.

### Detection
`is_device_features_table()` scores a table by counting peripheral keywords
("flash", "sram", "i2c", "spi", "uart", "adc", "dac", "tc", "pwm", ...) in
its header row or first column. Threshold ≥3 keyword hits.

### Orientation handling
Some datasheets (PIC32CM, AVR DU) have devices in **rows**, headers in row 0.
Some (PIC32CM JH, others) have devices in **columns**, features in row 0.
`detect_orientation()` counts how many "Microchip-prefix-looking part numbers"
appear in column 0 vs row 0 in the first 3 rows; whichever has more wins.
`normalize_table()` transposes if needed so devices are always in rows.

### Reversed-character text
Microchip PDFs render some column headers with **character order reversed**.
`hsalF\nyromeM\n)setyb(\nmargorP` is `Program (bytes) Memory Flash` reversed
character-by-character. `_unreverse_text()` and `_token_looks_reversed()`
detect this by counting how many common-English-keyword substrings appear
forward vs reversed. Each token in a header is checked independently so we
correctly handle mixed-orientation strings like `Timers tib-61` →
`Timers 16-bit`.

### Two-row headers
PIC24/dsPIC datasheets have **two-row headers**: row 0 is group labels
("Memory", "Peripherals"), row 1 is column names ("Program (bytes)",
"SRAM (bytes)"). `_is_continuation_header_row()` detects this pattern and
`_merge_header_rows()` joins the two rows into one usable header.

### Multi-part cells
Some tables put multiple part numbers in a single cell separated by `\n` or
`/` (e.g. `AVR16DU14\nAVR32DU14`). `_cell_contains_part()` splits and
matches per token.

### Variant row matching
`find_variant_row()` is a strict exact match — looks for the target part
number in column 0. The grep audit uses fuzzier matching (see scripts/
_count_wrong_pdfs_v2.py for variant generation: AT-prefix strip, trailing
revision letter strip, spaced/hyphenated forms).

## Stage 3: Features parser

[`datasheet_vectorizer/features_parser.py`](../datasheet_vectorizer/features_parser.py)

Every Microchip datasheet has a "Features" or "Microcontroller Features"
bullet list near page 1 with things that aren't always in the table:
- CPU type and max clock
- Voltage and temperature ranges
- Available packages
- Peripheral one-offs (USB type, RTC, WDT, BOR, POR)
- DAC/Op Amp/comparator counts when not tabled

A series of regex patterns tagged with the canonical field name they fill.
Tuple returns handle pairs like `(min, max)` for voltage.

## Stage 4: Field mapping

[`datasheet_vectorizer/vectorize.py`](../datasheet_vectorizer/vectorize.py)

Three dicts and a function:

- `RAW_TO_CANONICAL` — maps raw header strings (after normalization +
  un-reversing) to canonical field names. ~200 entries handling synonyms
  across PIC/AVR/SAM/dsPIC families.
- `RAW_TO_CANONICAL_MULTI` — maps raw keys that should populate multiple
  canonical fields (e.g. "8-bit DAC: 2" populates both Number_of_DACs and
  DAC_Outputs).
- `_norm_key()` — lowercases, collapses whitespace, strips ™/® symbols.
- Fuzzy fallback (substring match on common patterns) for unrecognized keys.

### Family defaults
`vectorize()` applies family-specific defaults that are usually correct
across the whole family:
- PIC16F1xxxx → CVD touch sensing, no hardware RTC
- AVR (most modern) → has hardware RTC
- PIC32CM/ATSAM → has RTC, no EEPROM
- AVR EB with WEX → Motor_Control_PWM=4

### Derivations
- `Timers_16bit` = TCA + TCB + TCE counts (TCF excluded — actually 24-bit)
- PIC `PWM_outputs` from `2/2` slash format: dedicated PWMs ≥4 → use that;
  otherwise sum PWM+CCP
- AVR-EB `USART/SPI host` cell counts as USART only (don't double-count)
- Pincount derivation from I/O pins via lookup table when not in table

## Discovery layer (scripts/)

The vectorizer needs to know which PDF goes with which part. That's the
discovery problem.

### Family bucketing
[`scripts/_family_groups.py`](../scripts/_family_groups.py) groups parts into
families by parsing the part number structure. Multiple iterations:
- v1: 336 buckets (too coarse — many distinct datasheets in one bucket)
- v2: 487 buckets (split by sub-family suffix like `_GA`, `_K22`)
- v3 (clusters): 868 part-level clusters (drop only trailing rev letter)

### URL discovery
We query Microchip's MCP server (`mcp__mchp_resources__search_microchip_product_documents`)
with a representative or specific part number. The response has a `url` field
on each document; if it ends in `.pdf` and contains `/DataSheets/` or
`/DeviceDoc/`, that's our datasheet URL. Falls back to parsing the document
body for `**Data Sheet**: [...](url.pdf)` markdown links.

The MCP queries were run via subagent batches (see
[docs/HANDOFF.md](HANDOFF.md) for re-running).

### Wrong-PDF audit
[`scripts/_count_wrong_pdfs_v2.py`](../scripts/_count_wrong_pdfs_v2.py) checks
whether each part's name actually appears in its assigned PDF's text. Uses
fuzzy variants: original, AT-prefix-stripped, trailing-rev-letter-stripped,
both-stripped, spaced, hyphenated. If none match, the part is flagged
`wrong_pdf: true` and its fields are nulled by `_null_wrong_pdf_parts.py`.

## Why it's not 99.6% accurate at scale

The README's 99.6% is the original tuning ground-truth (36 parts I'd already
seen). The real numbers from blind held-out validation:

- 89.7% of parts have a correctly-mapped PDF
- 73.3% per-cell accuracy on those parts

So realistic catalog-wide cell accuracy is roughly 65%. See
[ACCURACY.md](ACCURACY.md) for methodology.

The dominant error sources:
1. **Wrong-PDF assignment** (10.3% of parts, mostly irreducible — Microchip
   themselves list architecture manuals or ARM core TRMs as "datasheets" for
   AT32UC, XMEGA legacy, AT91SAM9 parts).
2. **Specific table layouts the parser hasn't been tuned for** — DAC counts,
   ADC channels, max temp range get mis-extracted often even when the right
   PDF is present.
3. **Family defaults masquerading as extracted data** for fields where the
   table doesn't explicitly list a value.
