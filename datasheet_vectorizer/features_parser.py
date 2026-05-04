"""
Features section parser — extract fields from the bulleted "Features" section
near the start of every Microchip datasheet.

Examples of patterns we look for:
- "Running at up to 24 MHz" -> CPU_Speed_Max_MHz=24
- "Supply voltage range: 1.8-5.5V" -> Voltage_Min=1.8, Voltage_Max=5.5
- "Temperature Ranges: Industrial: -40 C to +85 C" -> TempRange_Min=-40, TempRange_Max=85
- "ARM Cortex-M0+" / "AVR CPU" / "PIC CPU" -> CPU
- "Power-on Reset (POR)" -> POR=Yes
- "Brown-out Detector (BOD) with programmable levels" -> BOR=Programmable BOR
- "Watchdog Timer (WDT) with Window mode" -> WDT=Yes, Windowed_WDT=Yes
- "Real-Time Counter (RTC)" -> Hardware_RTC=Yes
- "USB 2.0 full-speed" -> USB=Full Speed, USB_Modules=1
- "14-pin SOIC and TSSOP" -> Packages=SOIC, TSSOP
"""

import re
from . import pdf_ingest


# Per-line patterns to extract specific fields. Each entry is (regex, field, transform).
PATTERNS = [
    # CPU type (ARM Cortex-M0+ first to grab the +)
    (r"Cortex[\W]*?(M0\+|M0|M1|M3|M4F|M4|M7|M23|M33|A5|A7|A53)",
     "CPU", lambda m: f"ARM Cortex-{m.group(1)}"),
    (r"\bAVR[®\s]+CPU\b", "CPU", lambda m: "AVR"),
    (r"\bPIC[®\s]+CPU\b", "CPU", lambda m: "PIC"),
    (r"\b(8|16|32)-bit\s+(PIC|AVR|MIPS)\b", "CPU", lambda m: f"{m.group(2)}"),

    # Speed (PIC: "DC-32 MHz clock input" or "DC – 32 MHz")
    (r"running at (?:up to |clock speeds up to )?(\d+(?:\.\d+)?)\s*MHz",
     "CPU_Speed_Max_MHz", lambda m: m.group(1)),
    (r"DC\s*[-–]\s*(\d+(?:\.\d+)?)\s*MHz", "CPU_Speed_Max_MHz", lambda m: m.group(1)),
    (r"DC\s+to\s+(\d+(?:\.\d+)?)\s*MHz", "CPU_Speed_Max_MHz", lambda m: m.group(1)),
    (r"DC\s+up\s+to\s+(\d+(?:\.\d+)?)\s*MHz", "CPU_Speed_Max_MHz", lambda m: m.group(1)),
    (r"CPU.{0,20}up\s+to\s+(\d+(?:\.\d+)?)\s*MHz", "CPU_Speed_Max_MHz", lambda m: m.group(1)),

    # Voltage range — capture both min and max
    (r"(?:Supply\s+)?voltage\s+range[:\s]+(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*V",
     "VOLTAGE_RANGE", lambda m: (m.group(1), m.group(2))),
    (r"(\d+(?:\.\d+)?)\s*V\s*[-–]\s*(\d+(?:\.\d+)?)\s*V",
     "VOLTAGE_RANGE", lambda m: (m.group(1), m.group(2))),

    # Temperature range
    (r"-40\s*[°]?\s*C?\s+to\s+\+?(\d+)\s*[°]?\s*C", "TEMP_MAX", lambda m: m.group(1)),
    (r"Industrial[:\s]+-40[°]?\s*C?\s+to\s+\+?(\d+)[°]?\s*C", "TEMP_INDUSTRIAL", lambda m: m.group(1)),
    (r"Extended[:\s]+-40[°]?\s*C?\s+to\s+\+?(\d+)[°]?\s*C", "TEMP_EXTENDED", lambda m: m.group(1)),

    # Reset / WDT
    (r"\bPower[\s-]on\s+Reset\b", "POR", lambda m: "Yes"),
    (r"Brown[\s-]?out\s+(?:Detector|Reset)[^.]*programmable", "BOR", lambda m: "Programmable BOR"),
    (r"Brown[\s-]?out\s+(?:Detector|Reset)\b(?!.*programmable)", "BOR", lambda m: "Yes"),
    (r"Watchdog\s+Timer.*?(?:Window\s+mode|Windowed)", "WINDOWED_WDT", lambda m: "Yes"),
    (r"Watchdog\s+Timer\b", "WDT", lambda m: "Yes"),
    (r"Real[\s-]?Time\s+Counter", "Hardware_RTC", lambda m: "Yes"),
    (r"Real[\s-]?Time\s+Clock", "Hardware_RTC", lambda m: "Yes"),

    # USB
    (r"\bUSB\s+2\.0\s+full[\s-]?speed\b", "USB", lambda m: "Full Speed"),
    (r"\bUSB\s+(?:Hi|High)[\s-]?Speed\b", "USB", lambda m: "Hi-Speed"),
    (r"\bfull[\s-]?speed\s+\(12\s*Mbps\)\s+device", "USB", lambda m: "Full Speed"),

    # Touch — require positive evidence (capacitive touch capability stated)
    (r"capacitive\s+touch\b", "Hardware_Touch", lambda m: "PTC"),
    (r"\bPTC\b.{0,80}capacitive", "Hardware_Touch", lambda m: "PTC"),
    (r"\bCVD\b.*?touch", "Hardware_Touch", lambda m: "CVD"),
    (r"Capacitive\s+Voltage\s+Divider", "Hardware_Touch", lambda m: "CVD"),
    (r"\bADC2\s+with\s+\w*CVD\b", "Hardware_Touch", lambda m: "CVD"),
    (r"ADC.{0,30}capacitive\s+sensing", "Hardware_Touch", lambda m: "CVD"),

    # CAN
    (r"\bCAN-FD\s+\(ISO", "CAN_CANFD", lambda m: "Yes"),

    # ADC resolution
    (r"(\d+)-bit[^.\n]{0,50}Analog-to-Digital", "ADC_Resolution_bits", lambda m: m.group(1)),
    (r"(\d+)-bit[^.\n]{0,50}ADC\b", "ADC_Resolution_bits", lambda m: m.group(1)),

    # DAC — count + resolution. Match "two 10-bit DACs", "one 10-bit DAC", or bare "10-bit ... DAC".
    (r"(?:Two|2)\s+(\d+)-bit\s+Digital-to-Analog", "DAC_INFO", lambda m: ("2", m.group(1))),
    (r"(\d+)\s+independent\s+(\d+)-bit\s+DACs?", "DAC_INFO", lambda m: (m.group(1), m.group(2))),
    (r"(?:One|1)\s+(\d+)-bit[^.\n]{0,80}Digital-to-Analog\s+Converter\s*\(DAC\)",
     "DAC_INFO", lambda m: ("1", m.group(1))),
    # Bare "10-bit, 350 ksps Digital-to-Analog Converter (DAC)" — assume 1
    (r"(\d+)-bit[^.\n]{0,80}Digital-to-Analog\s+Converter\s*\(DAC\)",
     "DAC_INFO", lambda m: ("1", m.group(1))),
    (r"(\d+)-bit\s+DAC\b", "DAC_INFO", lambda m: ("1", m.group(1))),

    # Op Amps
    (r"(?:up\s+to\s+)?(\d+|one|two|three|four)\s+Operational\s+Amplifiers?",
     "OPAMP_COUNT", lambda m: m.group(1).lower()),
    (r"(?:Single|One)\s+Operational\s+Amplifier", "OPAMP_COUNT", lambda m: "1"),
]


# Package detection — find list of supported packages
PACKAGE_KEYWORDS = ["TQFP", "VQFN", "SSOP", "SPDIP", "SOIC", "TSSOP", "PDIP", "QFN", "TFBGA", "LFBGA",
                    "WLCSP", "LQFP", "TQFP", "DIP"]


def _get_features_text(pdf_path, max_pages=8):
    """Get text from pages near the start that likely contain the features bullets."""
    pages = pdf_ingest.extract_layout_text(pdf_path, max_pages=max_pages)
    return "\n".join(pages)


def parse_packages(text):
    """Find list of mentioned packages."""
    pkgs = set()
    for kw in PACKAGE_KEYWORDS:
        if re.search(rf"\b{kw}\b", text):
            pkgs.add(kw)
    return sorted(pkgs)


def derive_cpu_from_part(part_number):
    """Fallback: infer CPU family from part number prefix."""
    if not part_number:
        return None
    p = part_number.upper()
    if p.startswith("PIC32CM") or p.startswith("ATSAMC"):
        return "ARM Cortex-M0+"  # most likely
    if p.startswith(("PIC16", "PIC18", "PIC12", "PIC10")):
        return "PIC"
    if p.startswith(("PIC24", "DSPIC30", "DSPIC33")):
        return "PIC24" if p.startswith("PIC24") else "dsPIC"
    if p.startswith("PIC32M"):
        return "MIPS32"
    if p.startswith(("AVR", "ATTINY", "ATMEGA", "ATXMEGA")):
        return "AVR"
    if p.startswith(("ATSAMD51", "ATSAME51", "ATSAME53", "ATSAME54")):
        return "ARM Cortex-M4F"
    if p.startswith(("ATSAMD", "ATSAMC", "ATSAML")):
        return "ARM Cortex-M0+"
    if p.startswith(("ATSAME70", "ATSAMS70", "ATSAMV70", "ATSAMV71")):
        return "ARM Cortex-M7"
    if p.startswith("SAMA7"):
        return "ARM Cortex-A7"
    return None


def _apply_field(out, field, val):
    """Apply a single regex match to the output dict. Used by temperature
    fields where multiple matches in the text need merging."""
    if field == "TEMP_MAX":
        out.setdefault("TempRange_Min", "-40")
        cur = out.get("TempRange_Max", "")
        try:
            if not cur or int(val) > int(cur):
                out["TempRange_Max"] = val
        except (ValueError, TypeError):
            out.setdefault("TempRange_Max", val)
    elif field == "TEMP_INDUSTRIAL":
        out.setdefault("TempRange_Min", "-40")
        cur = out.get("TempRange_Max", "")
        try:
            if not cur or int(val) > int(cur):
                out["TempRange_Max"] = val
        except (ValueError, TypeError):
            out.setdefault("TempRange_Max", val)
    elif field == "TEMP_EXTENDED":
        out.setdefault("TempRange_Min", "-40")
        cur = out.get("TempRange_Max", "")
        try:
            if not cur or int(val) > int(cur):
                out["TempRange_Max"] = val
        except (ValueError, TypeError):
            out["TempRange_Max"] = val


def parse_features(pdf_path, max_pages=8, target_part=None):
    """
    Run all patterns against the features text. Return dict of extracted fields.
    Optionally provide target_part for CPU inference fallback.
    """
    text = _get_features_text(pdf_path, max_pages=max_pages)
    out = {}

    for pattern, field, transform in PATTERNS:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if not matches:
            continue
        # For temperature fields, scan ALL matches and let the per-field handler
        # below pick the right one (e.g. take the maximum). For other fields,
        # first match is fine.
        if field in ("TEMP_MAX", "TEMP_INDUSTRIAL", "TEMP_EXTENDED"):
            for m in matches:
                try:
                    val = transform(m)
                except Exception:
                    continue
                _apply_field(out, field, val)
            continue
        m = matches[0]
        try:
            val = transform(m)
        except Exception:
            continue

        if field == "VOLTAGE_RANGE" and isinstance(val, tuple):
            v_min, v_max = val
            out.setdefault("Voltage_Min", v_min)
            out.setdefault("Voltage_Max", v_max)
        elif field == "TEMP_MAX":
            out.setdefault("TempRange_Min", "-40")
            # Prefer the highest max we see — handles datasheets that list multiple grades
            cur = out.get("TempRange_Max", "")
            try:
                if not cur or int(val) > int(cur):
                    out["TempRange_Max"] = val
            except (ValueError, TypeError):
                out.setdefault("TempRange_Max", val)
        elif field == "TEMP_INDUSTRIAL":
            out.setdefault("TempRange_Min", "-40")
            # Don't overwrite a higher (Extended) max
            if "TempRange_Max" not in out:
                out["TempRange_Max"] = val
        elif field == "TEMP_EXTENDED":
            # Extended supersedes industrial for max
            out["TempRange_Max"] = val
            out.setdefault("TempRange_Min", "-40")
        elif field == "WINDOWED_WDT":
            out.setdefault("WDT", "Yes")
            out.setdefault("Windowed_WDT", "Yes")
        elif field == "USB" and val:
            out.setdefault("USB", val)
            out.setdefault("USB_Modules", "1")
        elif field == "BOR":
            # "Programmable BOR" wins over "Yes"
            cur = out.get("BOR", "")
            if val == "Programmable BOR" or not cur:
                out["BOR"] = val
        elif field == "DAC_INFO" and isinstance(val, tuple):
            count, resolution = val
            out.setdefault("Number_of_DACs", count)
            out.setdefault("DAC_Outputs", count)  # most parts have 1 output per DAC
            out.setdefault("DAC_Resolution_Bits", resolution)
        elif field == "OPAMP_COUNT":
            word_to_num = {"one": "1", "two": "2", "three": "3", "four": "4",
                           "five": "5", "six": "6"}
            n = word_to_num.get(str(val).lower(), str(val))
            out.setdefault("Number_of_Op_Amps", n)
        else:
            if field not in out:
                out[field] = val

    # Packages
    pkgs = parse_packages(text[:4000])  # limit search to features section
    if pkgs:
        out["Packages"] = ", ".join(pkgs)

    # CPU fallback from part number
    if "CPU" not in out and target_part:
        cpu = derive_cpu_from_part(target_part)
        if cpu:
            out["CPU"] = cpu

    return out


if __name__ == "__main__":
    import sys
    pdf = sys.argv[1] if len(sys.argv) > 1 else "PIC32CMGV_datasheet.pdf"
    fields = parse_features(pdf)
    print(f"Features extracted from {pdf}:")
    for k, v in sorted(fields.items()):
        print(f"  {k}: {v}")
