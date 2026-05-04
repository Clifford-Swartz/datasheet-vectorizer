# Accuracy methodology and results

We've measured accuracy two different ways. They give very different numbers
and both are real. Read this before quoting either.

## TL;DR

| Test | Result |
|---|---|
| Tuning ground truth (36 parts I'd seen during development) | **744/747 = 99.6%** |
| Held-out blind validation (30 unseen parts × ~262 cells) | **73.3% per cell** on parts with correct PDF |
| Wrong-PDF rate (catalog-wide grep) | **231/2253 = 10.3%** |
| Realistic catalog-wide cell accuracy | ~65% |

## The tuning ground truth (don't quote this)

[`ground_truth.json`](../ground_truth.json) is 36 parts manually verified
across 7 family datasheets (AVR EB/DU/SD, PIC32CM GV, PIC16F 175/181/171).
Run [`_validate_phase1.py`](../scripts/_validate_phase1.py) to reproduce 99.6%.

This is **self-consistency**, not generalization. The parser was tuned by
running the validator, fixing errors, re-running. So passing it just means
the code matches what was decided during tuning. It doesn't say anything
about parts the parser hasn't been exposed to.

It's useful as a regression test ("did my refactor break anything I had
working?") but not as an accuracy claim.

## The honest test (held-out blind validation)

The protocol that produced the 73.3% number:

### 1. Sample selection
[`_pick_holdout.py`](../scripts/_pick_holdout.py) picked 30 parts from
`vectorized_all.json` that were **not** in `ground_truth.json`, stratified
across families I'd never tuned for (PIC18 K-series, PIC24 GU/GL, dsPIC33
CK/EP/CH/EV, ATSAM legacy, ATTINY, ATXMEGA, etc.).

### 2. Vectorize each held-out part
The vectorizer's outputs for those 30 parts — that's the prediction.

### 3. Independent blind verification
Three subagents were given the PDFs and the field names, but **not** our
extracted values. Each agent independently read each PDF and recorded what
the datasheet actually says for each field. Stored in
`verify_results_batch{1,2,3}.json`.

The blindness is the important part. The verifier doesn't know what we
extracted, so it can't unconsciously rationalize our value.

### 4. Cell-by-cell comparison
[`_compute_honest_accuracy.py`](../scripts/_compute_honest_accuracy.py)
joins the verifier's findings against `vectorized_all.json` and counts
cell-level matches.

### 5. Two findings

**(a) Wrong-PDF rate: 50% (15/30) of held-out parts were in the wrong PDF**

The verifier couldn't find the part in the assigned PDF for half the sample.
That means: our family-key bucketing put parts on a datasheet that doesn't
contain them. The vectorizer still returned ~16 fields/part for those —
those values came from family defaults + features-bullet contamination from
the wrong PDF, not real per-variant extraction.

We confirmed by direct text grep: `DSPIC33CK32MP502` does not appear
anywhere in `dsPIC33CK1024MP710-Family-Data-Sheet-DS70005496.pdf`.

**(b) Per-cell accuracy on correct-PDF parts: 73.3%** (110/150 cells)

For the 15 parts where the verifier could find values, our vectorizer matched
the datasheet on 73% of cells. Worst fields:
- TempRange_Max: 38%
- ADC_Channels: 33%
- Number_of_DACs: 53%
- Program_Memory_KB: 50%

Strongest: Pincount, IO_Pins_Max, RAM_KB, SPI, WDT, Hardware_RTC,
TempRange_Min — all 100% on samples where they were present.

## Catalog-wide wrong-PDF audit

Held-out test gives ~50% wrong-PDF on 30 parts. To get the catalog-wide
number, [`_count_wrong_pdfs_v2.py`](../scripts/_count_wrong_pdfs_v2.py)
extracts plain text from each unique PDF and checks whether each assigned
part's name appears (with fuzzy variants for AT-prefix and revision-letter
suffixes). If not, the part is wrong-PDF.

Audit progression as we fixed the discovery layer:
- Initial 336-bucket family-key: **977/2253 = 43.4% wrong-PDF**
- After splitting to 487 sub-families: same 977 (the 487 split fixed
  cross-family bleed but not within-family granularity)
- After 868 part-level clusters + MCP rediscovery: **407 = 18.1%**
- After fuzzy grep audit (AT-prefix + rev-letter strip): **294 = 13.0%**
- After retry agent on dropped clusters: **231 = 10.3%**

The remaining 231 break into:
- 56 AT32UC parts → `doc32000.pdf` (AVR 32-bit Architecture Manual; Microchip's
  product page lists this as the "Data Sheet" for these chips)
- ~50 XMEGA legacy → AVR XMEGA manuals (same situation — no per-variant DS)
- ~20 AT91SAM9/SAM7 → ARM core technical reference manuals
- The rest are family datasheets that genuinely don't list specific variants
  the catalog includes

Most of these are **structurally unfixable** without a different data source.

## Two derived honesty improvements

1. **Wrong-PDF parts now have empty `fields: {}` and a `wrong_pdf: true` flag**
   in `vectorized_all.json`. They used to have ~16 fields/part of contamination
   that looked like real data.

2. **Coverage stats are now true coverage** (parts with extracted data),
   not "parts where any default was filled". Pre-fix, fields like
   `Auxiliary_Flash_KB` were at 96.4% (looked rich) but mostly were the
   default value `0`. Post-fix, that field's coverage equals the right-PDF
   rate (89.7%) because we apply defaults only when we have a real PDF.

## Re-running the held-out test

To test on a fresh sample (you should — anyone reading this should):

```bash
python scripts/_pick_holdout.py            # picks 30 new held-out parts
python scripts/_build_verification_tasks.py # creates verify_blind_batch{1,2,3}.json
# Pass each blind batch to a fresh subagent / human verifier with the PDFs
# Save their findings as verify_results_batch{1,2,3}.json
python scripts/_compute_honest_accuracy.py # produces the cell-level report
```

If you change the parser, this is the test that tells you whether you've
actually improved accuracy or just over-fit to the tuning set.
