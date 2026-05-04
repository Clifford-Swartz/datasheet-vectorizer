"""
Validate Phase 1 vectorizer against ground_truth.json
For each verified part, run the vectorizer and compare to ground truth.
"""

import json
import sys
import re
sys.path.insert(0, '.')
from datasheet_vectorizer import vectorize


# Map ground-truth part -> datasheet PDF
PART_TO_PDF = {
    # AVR EB family
    "AVR16EB14": "AVR16EB14_datasheet.pdf",
    "AVR16EB20": "AVR16EB14_datasheet.pdf",
    "AVR16EB28": "AVR16EB14_datasheet.pdf",
    # AVR DU family
    "AVR16DU14": "AVR16DU_datasheet.pdf",
    "AVR16DU20": "AVR16DU_datasheet.pdf",
    "AVR16DU28": "AVR16DU_datasheet.pdf",
    "AVR16DU32": "AVR16DU_datasheet.pdf",
    "AVR32DU14": "AVR16DU_datasheet.pdf",
    "AVR32DU20": "AVR16DU_datasheet.pdf",
    "AVR32DU28": "AVR16DU_datasheet.pdf",
    "AVR32DU32": "AVR16DU_datasheet.pdf",
    # AVR SD family
    "AVR32SD20": "AVR32SD_datasheet.pdf",
    "AVR32SD28": "AVR32SD_datasheet.pdf",
    # PIC32CM GV family
    "PIC32CM1602GV00032": "PIC32CMGV_datasheet.pdf",
    "PIC32CM3204GV00032": "PIC32CMGV_datasheet.pdf",
    "PIC32CM1602GV00048": "PIC32CMGV_datasheet.pdf",
    "PIC32CM3204GV00048": "PIC32CMGV_datasheet.pdf",
    "PIC32CM1602GV00064": "PIC32CMGV_datasheet.pdf",
    "PIC32CM3204GV00064": "PIC32CMGV_datasheet.pdf",
    # PIC16F175x family
    "PIC16F17526": "PIC16F17526_datasheet.pdf",
    "PIC16F17554": "PIC16F17526_datasheet.pdf",
    "PIC16F17555": "PIC16F17526_datasheet.pdf",
    "PIC16F17556": "PIC16F17526_datasheet.pdf",
    "PIC16F17546": "PIC16F17526_datasheet.pdf",
    "PIC16F17574": "PIC16F17526_datasheet.pdf",
    "PIC16F17575": "PIC16F17526_datasheet.pdf",
    "PIC16F17576": "PIC16F17526_datasheet.pdf",
    # PIC16F181x family
    "PIC16F18114": "PIC16F18175_datasheet.pdf",
    "PIC16F18124": "PIC16F18175_datasheet.pdf",
    "PIC16F18125": "PIC16F18175_datasheet.pdf",
    "PIC16F18154": "PIC16F18175_datasheet.pdf",
    "PIC16F18175": "PIC16F18175_datasheet.pdf",
    "PIC16F18176": "PIC16F18175_datasheet.pdf",
    # PIC16F171x family
    "PIC16F17124": "PIC16F17175_datasheet.pdf",
    "PIC16F17175": "PIC16F17175_datasheet.pdf",
    "PIC16F17176": "PIC16F17175_datasheet.pdf",
}


# Map ground_truth field name -> vectorizer canonical field name
# (some are direct, some need transformation)
GT_TO_CANONICAL = {
    "CPU": None,  # not in tables
    "CPU_Speed_Max_MHz": "CPU_Speed_Max_MHz",
    "Program_Memory_KB": "Program_Memory_KB",
    "Auxiliary_Flash_KB": "Auxiliary_Flash_KB",
    "RAM_KB": "RAM_KB",
    "EEPROM_bytes": "EEPROM_bytes",
    "IO_Pins_Max": "IO_Pins_Max",
    "Pincount": "Pincount",
    "I2C": "I2C",
    "SPI": "SPI",
    "USART": "USART",
    "ADC_Channels": "ADC_Channels",
    "Number_of_Comparators": "Number_of_Comparators",
    "Number_of_Op_Amps": "Number_of_Op_Amps",
    "Number_of_DACs": "Number_of_DACs",
    "DAC_Outputs": "DAC_Outputs",
    "CCL_LUTs": "CCL_LUTs",
    "Hardware_Touch": "Hardware_Touch",
    "Hardware_RTC": "Hardware_RTC",
    "WDT": "WDT",
    "Timers_16bit": "Timers_16bit",
    "PWM_outputs": "PWM_outputs",
    "CCP": "CCP",
}


def normalize_value(v):
    if v is None: return ""
    s = str(v).strip()
    if s.lower() in ("none","n/a","null","-","—"): return ""
    if re.match(r"^\d+\.0+$", s):
        s = str(int(float(s)))
    return s


def values_match(a, b):
    a, b = normalize_value(a), normalize_value(b)
    if a == b: return True
    if not a and not b: return True
    try:
        if abs(float(a) - float(b)) < 0.01: return True
    except (ValueError, TypeError): pass
    if a.lower() == b.lower(): return True
    return False


def main():
    gt = json.load(open("ground_truth.json"))
    verified = [p for p, d in gt.items() if "CPU" in d and "NEEDS" not in d.get("source", "")]

    total_correct = 0
    total_wrong = 0
    total_missing = 0
    per_part_results = []
    field_failures = {}

    for part in verified:
        if part not in PART_TO_PDF:
            print(f"SKIP {part}: no PDF mapping")
            continue
        pdf = PART_TO_PDF[part]
        result = vectorize.vectorize(pdf, part, max_pages=15)
        extracted = result["fields"]

        c, w, m = 0, 0, 0
        wrong_fields = []
        for gt_field, canon in GT_TO_CANONICAL.items():
            if canon is None: continue
            if gt_field not in gt[part]: continue
            truth = gt[part][gt_field]
            if not str(truth).strip():
                continue  # skip empty truth
            ours = extracted.get(canon, "")
            if not ours:
                m += 1
                wrong_fields.append((gt_field, truth, "MISSING"))
                field_failures.setdefault(gt_field, [0,0])[1] += 1
            elif values_match(truth, ours):
                c += 1
                field_failures.setdefault(gt_field, [0,0])[0] += 1
            else:
                w += 1
                wrong_fields.append((gt_field, truth, ours))
                field_failures.setdefault(gt_field, [0,0])[1] += 1

        total = c + w + m
        per_part_results.append((part, c, w, m, total, wrong_fields))
        total_correct += c
        total_wrong += w
        total_missing += m

    # Print per-part
    per_part_results.sort(key=lambda x: x[1] / max(x[4], 1))
    print(f"{'Part':<25} {'Correct':>7} {'Wrong':>5} {'Miss':>5} {'Total':>5} {'Acc':>6}")
    print("-" * 60)
    for part, c, w, m, t, _ in per_part_results:
        acc = c / max(t, 1) * 100
        print(f"{part:<25} {c:>7} {w:>5} {m:>5} {t:>5} {acc:>5.1f}%")

    grand = total_correct + total_wrong + total_missing
    print()
    print(f"GRAND TOTAL: {total_correct}/{grand} correct ({total_correct/grand*100:.1f}%)")
    print(f"  Correct: {total_correct}")
    print(f"  Wrong:   {total_wrong}")
    print(f"  Missing: {total_missing}")

    print()
    print("Per-field correctness:")
    for f, (cor, wm) in sorted(field_failures.items(), key=lambda x: -x[1][0]):
        tot = cor + wm
        print(f"  {f:<25} {cor}/{tot}  ({cor/max(tot,1)*100:.0f}%)")

    print()
    print("Worst 5 parts (sample errors):")
    for part, c, w, m, t, errs in per_part_results[:5]:
        print(f"\n  {part} ({c}/{t}):")
        for f, truth, ours in errs[:8]:
            print(f"    {f}: truth={truth!r} ours={ours!r}")


if __name__ == "__main__":
    main()
