"""
Group all 2,311 parts in the parts spreadsheet into families.
Each "family" should map to a single datasheet PDF (mostly).
Outputs families.json: {family_key: {representative: PART, parts: [PART...]}}
"""
import openpyxl
import re
import json


def family_key(p):
    """Map a part number to the family stem most likely to share a datasheet."""
    p = p.upper()

    # PIC32xx — modern: PIC32CM, PIC32MX, PIC32MZ, PIC32CK, PIC32CZ, PIC32CX, PIC32WK, PIC32WM, PIC32MK
    # Pattern: PIC32<TYPE><MEMORY><SUBFAM><PINS> e.g. PIC32CM 1216 LE 00048
    m = re.match(r"^(PIC32[A-Z]{1,2})(\d+)([A-Z]+)\d*$", p)
    if m:
        return f"{m.group(1)}_{m.group(3)}"

    # PIC32M older with simpler tail: PIC32MX110F016B
    m = re.match(r"^(PIC32M[XZK])(\d{3})", p)
    if m:
        # group by first digit (PIC32MX1xx, PIC32MX2xx, ...)
        return f"{m.group(1)}{m.group(2)[0]}xx"

    # dsPIC33A/C/E/F variants — pattern: DSPIC33<ARCH><MEM><SUB><PINS>
    # Example: DSPIC33CK256MC506 -> arch=CK, mem=256, sub=MC, pins=506
    # The sub-family (MC, MP, GP, GS, EV, EP, etc.) determines the datasheet.
    m = re.match(r"^(DSPIC\d{2}[A-Z]+)\d+([A-Z]+)\d*$", p)
    if m:
        return f"{m.group(1)}_{m.group(2)}"

    # dsPIC33 fallback if no sub-family suffix
    m = re.match(r"^(DSPIC\d{2}[A-Z]+)(\d+)", p)
    if m:
        return m.group(1)

    # dsPIC30F — pattern: DSPIC30F<MEM><SUB>?
    m = re.match(r"^(DSPIC30F)\d+([A-Z]+)?\d*$", p)
    if m:
        sub = m.group(2)
        return f"{m.group(1)}_{sub}" if sub else m.group(1)
    m = re.match(r"^(DSPIC30F)(\d+)", p)
    if m:
        return m.group(1)

    # PIC10/12/16/18/24F families — sub-family identifier
    # Example: PIC24FJ128GA702 -> prefix=PIC24FJ, mem=128, sub=GA702
    #          PIC18F46Q10     -> prefix=PIC18F,  mem=46,  sub=Q10
    #          PIC18F25K22     -> prefix=PIC18F,  mem=25,  sub=K22
    #          PIC16F18175     -> prefix=PIC16F,  mem=181, sub='75'  (no letter)
    # For PIC18/PIC24, the letter+digits after memory is the datasheet identifier.
    m = re.match(r"^(PIC\d{2}[A-Z]+)\d+([A-Z]+\d{1,3})$", p)
    if m:
        return f"{m.group(1)}_{m.group(2)}"

    # PIC16Fxxxxx, PIC10F202 — usually no letter sub, group by memory prefix
    m = re.match(r"^(PIC\d{2}[A-Z]+)(\d+)$", p)
    if m:
        digits = m.group(2)
        # 5-digit parts (PIC16F18175): group by first 3 digits
        if len(digits) >= 5:
            return f"{m.group(1)}{digits[:3]}xx"
        # 3-digit parts (PIC16F505): group by first 2 digits
        if len(digits) == 3:
            return f"{m.group(1)}{digits[:2]}x"
        return f"{m.group(1)}{digits}"

    # Fallback: PIC family with no sub-suffix
    m = re.match(r"^(PIC\d{2}[A-Z]+)(\d+)", p)
    if m:
        digits = m.group(2)
        return f"{m.group(1)}{digits[:3]}xx"

    # AVRnn<FAM><PINS>: AVR64SD28 -> AVR_SD; AVR16EB14 -> AVR_EB
    m = re.match(r"^AVR\d+([A-Z]+)\d*", p)
    if m:
        return f"AVR_{m.group(1)}"

    # ATTINYnnnn / ATMEGAnnnn  -> by first digit (ATTINY1xxx, ATMEGA3xxx)
    m = re.match(r"^(ATTINY|ATMEGA)(\d+)", p)
    if m:
        return f"{m.group(1)}{m.group(2)[0]}xxx"

    # ATSAMxx with optional letter and digits, e.g. ATSAMD21G18A, ATSAML10E14, ATSAMA5D29-TA100
    m = re.match(r"^(ATSAM[A-Z]?\d+)", p)
    if m:
        return m.group(1)

    # SAM (no AT prefix), SAMA7D65, SAMA5D2 etc.
    m = re.match(r"^(SAM[A-Z]?\d+)", p)
    if m:
        return m.group(1)

    # ATXMEGAxx
    m = re.match(r"^(ATXMEGA)(\d+)", p)
    if m:
        return f"{m.group(1)}{m.group(2)[0]}xx"

    # AT89/AT90/AT91, AT32UC3, ATUC3
    m = re.match(r"^(AT\d{2}[A-Z]+)", p)
    if m:
        return m.group(1)
    m = re.match(r"^(ATUC)(\d+)", p)
    if m:
        return f"{m.group(1)}{m.group(2)[0]}"

    # MTR
    return p[:6]


def build_families(xlsx_path):
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active
    parts = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0]:
            parts.append(str(row[0]).strip().upper())

    families = {}
    for p in parts:
        f = family_key(p)
        if f not in families:
            families[f] = {"representative": p, "parts": []}
        families[f]["parts"].append(p)

    return families


if __name__ == "__main__":
    families = build_families("Copy of ChartData_FILLED_FIXED_FIXED.xlsx")
    print(f"Total families: {len(families)}")
    print(f"Total parts: {sum(len(f['parts']) for f in families.values())}")

    # Sort and write
    sorted_fams = dict(sorted(families.items(), key=lambda x: -len(x[1]["parts"])))
    with open("families.json", "w") as f:
        json.dump(sorted_fams, f, indent=2)
    print("Wrote families.json")

    # Singletons
    singletons = sum(1 for f in families.values() if len(f["parts"]) == 1)
    print(f"Singletons: {singletons}")
