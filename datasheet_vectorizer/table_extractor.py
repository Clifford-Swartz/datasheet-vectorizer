"""
Table extraction — find and parse the Configuration Summary / Family Features tables.
These tables list device variants in rows (or columns) with peripheral counts.
"""

import re
from . import pdf_ingest


# Header keywords that indicate a "device features" table (any one of these in row 1)
DEVICE_HEADER_KEYWORDS = [
    "device", "p/n", "part number", "pin count", "pins",
]

# Feature column keywords — if we see these, it's likely the table we want
FEATURE_KEYWORDS = [
    "flash", "sram", "ram", "eeprom", "i2c", "spi", "uart", "usart",
    "adc", "dac", "tc", "tcc", "tcb", "tca", "ac", "ptc", "ccl", "lut",
    "timer", "comparator", "op amp", "opamp",
    "ccp", "pwm", "i/o", "io",
]


def _normalize_for_keyword_search(text):
    """
    Some PDF tables come out with reversed-character headers
    (e.g., 'eciveD' instead of 'Device'). Concatenate forward + reversed
    so keyword search hits either way.
    """
    if not text:
        return ""
    return text.lower() + " " + text.lower()[::-1]


def _row_score(row, keywords):
    """How many keywords appear in this row (case-insensitive, handles reversed text)."""
    if not row:
        return 0
    text = " ".join(str(c) for c in row if c)
    text_search = _normalize_for_keyword_search(text)
    return sum(1 for kw in keywords if kw in text_search)


_COMMON_WORDS = [
    "device", "memory", "ram", "flash", "pin", "pins", "i/o", "data", "byte", "bytes", "kbyte", "kbytes",
    "program", "i2c", "spi", "uart", "usart", "eusart", "adc", "dac", "timer",
    "timers", "comparator", "comparators", "ccp", "pwm", "ccl", "clc", "rtc",
    "rtcc", "wdt", "watchdog", "external", "interrupt", "package", "channel",
    "channels", "frequency", "voltage", "temperature", "ports", "module",
    "modules", "crc", "scan", "indicator", "debug", "reference", "input",
    "output", "peripheral", "gpio", "eeprom", "sram", "operational",
    "amplifier", "touch", "ptc", "pps", "hlvd", "dsm", "zcd", "cwg", "lvd",
    "mssp", "tmr", "tca", "tcb", "tcc", "tcd", "tce", "tcf", "windowed",
    "pll", "qei", "quadrature", "encoder", "supply", "operating",
    "address", "line", "detect", "cross", "zero", "low", "high", "bit",
    "bits", "with", "include", "instructions", "instruction", "set", "size",
    "type", "extended", "core", "configuration",
]


def _word_score(s):
    """How many common-word substrings are in s (case-insensitive)."""
    s_low = s.lower()
    return sum(1 for w in _COMMON_WORDS if w in s_low)


def _looks_reversed(s):
    """True if reversing the string produces more recognizable English keywords."""
    if not s:
        return False
    return _word_score(s[::-1]) > _word_score(s)


def _token_looks_reversed(s):
    """For an individual whitespace-separated token, more aggressive: unreverse
    if the reversed form matches a common word AND the forward form doesn't.
    This catches single-word reversals like 'tceteD' (=Detect), 'elbasiD' (=Disable),
    where both forms might have zero or equal matches in the broader heuristic but
    only one is real English."""
    if not s or len(s) < 3:
        return False
    s_low = s.lower()
    # Strip non-letter chars for the keyword check (handles ')setyb(' = '(bytes)')
    clean = "".join(c for c in s_low if c.isalpha())
    rev_clean = clean[::-1]
    if not clean:
        return False
    f_match = any(w == clean or (len(w) >= 4 and w in clean) for w in _COMMON_WORDS)
    r_match = any(w == rev_clean or (len(w) >= 4 and w in rev_clean) for w in _COMMON_WORDS)
    return r_match and not f_match


def _unreverse_text(s):
    """Unreverse a header cell if it looks reversed.

    Two-pass strategy:
      1. Whole-string check: if reversing the entire string scores better, reverse it.
      2. Per-token check: for any remaining tokens whose reversed form matches a
         known word but whose forward form doesn't, unreverse just that token.
         This catches mixed strings like 'Flash Memory )setyb( Program' where
         '(bytes)' is the only reversed token left.
    """
    if not s:
        return s
    s_clean = str(s).strip()
    if _looks_reversed(s_clean):
        s_clean = s_clean[::-1]
    parts = re.split(r"(\s+)", s_clean)
    out = []
    for p in parts:
        if p.strip() and _token_looks_reversed(p):
            out.append(p[::-1])
        else:
            out.append(p)
    return "".join(out)


def is_device_features_table(table):
    """
    Decide if this table is a 'device features' table.
    Looks for: device names in column 1, peripheral keywords in headers.
    """
    if not table or len(table) < 2:
        return False

    header = table[0]
    if not header:
        return False

    # Normal orientation: header has feature names, column 1 has device names
    header_score_normal = _row_score(header, FEATURE_KEYWORDS + DEVICE_HEADER_KEYWORDS)

    # Transposed orientation: header has device names, column 1 has feature names
    first_col = [row[0] for row in table if row]
    feature_col_score = _row_score(first_col, FEATURE_KEYWORDS)

    return header_score_normal >= 3 or feature_col_score >= 3


def detect_orientation(table):
    """
    Returns 'rows' if devices are in rows (normal), 'columns' if devices are in columns (transposed).
    Detection: count part-number-looking strings in first column vs first row.
    Cells may have multiple part numbers separated by newlines (e.g., 'AVR16DU14\\nAVR32DU14').
    """
    if not table or len(table) < 2:
        return "rows"

    # Microchip part-number prefixes
    PART_PREFIXES = (
        "PIC", "DSPIC", "AVR", "ATTINY", "ATMEGA", "ATSAM", "ATSAME",
        "ATSAMD", "ATSAMC", "ATSAML", "ATSAMV", "ATSAMS", "ATSAMA",
        "AT89", "AT90", "AT91", "ATXMEGA", "SAM", "SAMA", "SAMS",
        "PIC32", "PIC18", "PIC16", "PIC24", "PIC10", "PIC12",
    )

    def count_parts_in_cell(s):
        """Count distinct part-number-looking tokens in a cell."""
        if not s:
            return 0
        s = str(s).strip()
        # Split on newlines, slashes, commas
        tokens = re.split(r"[\n,/]+", s)
        n = 0
        for tok in tokens:
            tok = tok.strip().upper()
            if len(tok) < 6:
                continue
            if not any(c.isdigit() for c in tok):
                continue
            if not any(c.isalpha() for c in tok):
                continue
            # Must start with one of the known prefixes
            if not any(tok.startswith(p) for p in PART_PREFIXES):
                continue
            n += 1
        return n

    # Check first column across all rows
    first_col = [row[0] for row in table if row]
    col_part_count = sum(count_parts_in_cell(c) for c in first_col)

    # Check first few rows for "device row" - sometimes header is row 0 or row 1
    row_part_count = 0
    for r_idx in range(min(3, len(table))):
        row = table[r_idx]
        if not row:
            continue
        cells = list(row[1:])
        rc = sum(count_parts_in_cell(c) for c in cells)
        row_part_count = max(row_part_count, rc)

    if col_part_count > row_part_count:
        return "rows"
    elif row_part_count > col_part_count:
        return "columns"
    return "rows"  # default


def _find_header_row(table):
    """Find the row that's most likely the actual header (devices in cols or features in row 0).
    Returns index of header row.
    """
    for i, row in enumerate(table[:3]):
        if row and any(c and str(c).strip() and str(c).strip() != "None" for c in row):
            # Skip rows that are just titles like "Table 2..." or "...continued"
            non_empty = [c for c in row if c and str(c).strip()]
            if len(non_empty) >= 2:
                # Looks like a real header row
                return i
    return 0


def _is_continuation_header_row(row):
    """A row that looks like the second line of a two-row header:
    - first cell is None or empty (the device-name column has nothing here)
    - has multiple non-empty feature-keyword cells.
    Used in PIC24/dsPIC datasheets where row 0 has group labels (Memory, Peripherals)
    and row 1 has the actual column names beneath them."""
    if not row or len(row) < 3:
        return False
    first = row[0]
    if first and str(first).strip() and str(first).strip() != "None":
        return False
    cells = [str(c).strip() for c in row[1:] if c and str(c).strip()]
    if len(cells) < 3:
        return False
    return _row_score(cells, FEATURE_KEYWORDS) >= 2


def _merge_header_rows(top, bottom):
    """Merge a two-row header. For each column, prefer the bottom (specific) cell;
    if bottom is empty/None, fall back to top (group label). Concatenate when both present
    so e.g. group='Memory' + col='Program (bytes)' → 'Memory Program (bytes)'."""
    n = max(len(top), len(bottom))
    merged = []
    for i in range(n):
        t = top[i] if i < len(top) else None
        b = bottom[i] if i < len(bottom) else None
        t_s = str(t).strip() if t else ""
        b_s = str(b).strip() if b else ""
        if not b_s:
            merged.append(t_s)
        elif not t_s:
            merged.append(b_s)
        else:
            merged.append(b_s)  # bottom is the specific column name; prefer it
    return merged


def normalize_table(table, orientation):
    """
    Convert any table to rows-of-devices format.
    Returns: (header, rows) where header is list of feature names, rows is list of [device, val, val...]
    Handles 'continued' tables where row 0 is junk like 'Table X. ...continued',
    and two-row headers (PIC24/dsPIC) where row 0 is group labels and row 1 is column names.
    """
    if not table:
        return [], []

    header_idx = _find_header_row(table)
    table = table[header_idx:]

    if orientation == "columns":
        # Transpose
        max_len = max(len(r) for r in table) if table else 0
        transposed = []
        for col_idx in range(max_len):
            new_row = []
            for row in table:
                new_row.append(row[col_idx] if col_idx < len(row) else None)
            transposed.append(new_row)
        table = transposed

    if not table:
        return [], []

    header = table[0]
    rows = table[1:]

    # If row 0 of `rows` looks like a continuation header line (PIC24/dsPIC pattern),
    # merge it into the header and drop it from data rows.
    if rows and _is_continuation_header_row(rows[0]):
        header = _merge_header_rows(header, rows[0])
        rows = rows[1:]

    return header, rows


def find_device_features_tables(pdf_path, max_pages=20):
    """
    Find all tables in the first N pages that look like device features tables.
    Returns list of {page, header, rows, orientation, raw_table}
    Note: 'orientation' is the ORIGINAL orientation; after normalize_table the
    structure is always devices-in-rows.
    """
    raw_tables = pdf_ingest.extract_tables_pdfplumber(pdf_path, max_pages=max_pages)
    found = []
    for t in raw_tables:
        table = t["data"]
        if is_device_features_table(table):
            orient = detect_orientation(table)
            header, rows = normalize_table(table, orient)
            found.append({
                "page": t["page"],
                "header": header,
                "rows": rows,
                "orientation_original": orient,
                "raw": table,
            })
    return found


def _cell_contains_part(cell, target):
    """Check if a cell (which may have multiple parts on newlines) contains target."""
    if not cell:
        return False
    target_up = target.upper().strip()
    for tok in re.split(r"[\n,/\s]+", str(cell)):
        tok = tok.strip().upper()
        if tok == target_up:
            return True
    return False


def find_variant_row(table_info, target_part):
    """
    Find the row in the table matching the target part number.
    After normalize_table, devices are always in rows (column 0).
    Handles cells with multiple parts (e.g., 'AVR16DU14\\nAVR32DU14').
    Returns: dict mapping header_field -> value, or None if not found.
    """
    header = table_info["header"]
    rows = table_info["rows"]

    # Exact-cell match (handles multi-part cells)
    for row in rows:
        if not row:
            continue
        if _cell_contains_part(row[0], target_part):
            return _row_to_dict(header, row)

    # Fallback: substring match
    for row in rows:
        if not row or not row[0]:
            continue
        first = str(row[0]).strip().upper()
        if target_part.upper() in first or first in target_part.upper():
            return _row_to_dict(header, row)

    return None


def extract_all_for_part(pdf_path, target_part, max_pages=20):
    """
    Look at all device features tables and merge any that match the target part.
    Returns: merged dict of {feature: value}, plus list of (page, table_idx) sources.
    """
    tables = find_device_features_tables(pdf_path, max_pages=max_pages)
    merged = {}
    sources = []
    for ti, t in enumerate(tables):
        match = find_variant_row(t, target_part)
        if match:
            sources.append((t["page"], ti))
            for k, v in match.items():
                # Don't overwrite existing values with empty
                if v and (k not in merged or not merged[k]):
                    merged[k] = v
    return merged, sources


def _clean_header_cell(h):
    """Unreverse a header cell, preserving word order. For multi-line headers,
    unreverse each line independently so words read top-to-bottom in natural order."""
    if h is None:
        return ""
    s = str(h)
    if "\n" in s:
        # Unreverse each line separately, then join. Each line was reversed
        # character-by-character in the source PDF, so per-line unreversal
        # restores natural reading order.
        lines = [_unreverse_text(line) for line in s.split("\n")]
        return " ".join(line for line in lines if line).strip()
    return _unreverse_text(s).strip()


def _row_to_dict(header, row):
    """Zip header with row, skipping None header cells. Un-reverses headers if needed."""
    result = {}
    for h, v in zip(header, row):
        if h is None:
            continue
        h_clean = _clean_header_cell(h)
        v_clean = str(v).strip() if v else ""
        if h_clean:
            result[h_clean] = v_clean
    return result


if __name__ == "__main__":
    import sys
    pdf = sys.argv[1] if len(sys.argv) > 1 else "PIC32CMGV_datasheet.pdf"
    target = sys.argv[2] if len(sys.argv) > 2 else "PIC32CM5164LE00048"

    print(f"Finding device features tables in {pdf}...")
    tables = find_device_features_tables(pdf)
    print(f"Found {len(tables)} candidate table(s).\n")

    for i, t in enumerate(tables):
        print(f"=== Table {i} (page {t['page']}, orig_orient={t['orientation_original']}) ===")
        print(f"Header: {t['header']}")
        print(f"Rows: {len(t['rows'])}")
        for row in t['rows'][:3]:
            print(f"  {row}")
        print()

    print(f"\nLooking for {target} (merged across all tables)...")
    merged, sources = extract_all_for_part(pdf, target)
    if merged:
        print(f"Sources: {sources}")
        for k, v in merged.items():
            print(f"  {k}: {v!r}")
    else:
        print("NOT FOUND in any table.")
