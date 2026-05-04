"""
Main orchestrator: PDF + part number -> structured parametric JSON.
Phase 1: Table-based extraction.
Phase 2: + Features section regex parsing.
"""

import json
import re
from . import table_extractor, features_parser


# Map raw extracted table fields (after un-reversing) to canonical DB column names.
# Multiple raw names can map to the same canonical (we pick the first non-empty).
# Some raw keys should populate multiple canonical fields (e.g., "8-bit DAC: 2" -> both Number_of_DACs and DAC_Outputs)
RAW_TO_CANONICAL_MULTI = {
    "10-bit dac": ["Number_of_DACs", "DAC_Outputs"],
    "8-bit dac": ["Number_of_DACs", "DAC_Outputs"],
    "12-bit dac": ["Number_of_DACs", "DAC_Outputs"],
}

RAW_TO_CANONICAL = {
    # Memory
    "flash memory": "Program_Memory_KB",
    "flash": "Program_Memory_KB",
    "program flash memory": "Program_Memory_KB",
    "program flash memory (bytes)": "Program_Memory_KB",
    "program flash": "Program_Memory_KB",
    "program (bytes)": "Program_Memory_KB",  # PIC24/dsPIC two-row header form
    "sram": "RAM_KB",
    "data sram (bytes)": "RAM_KB",
    "data memory (kb)": "RAM_KB",
    "ram": "RAM_KB",
    "(bytes) sram": "RAM_KB",  # PIC24/dsPIC merged-header form
    "data (bytes)(2) sram": "RAM_KB",  # PIC18 unreversed-header form
    "sram (bytes)(2) data": "RAM_KB",  # PIC18 unreversed (whole reversed)
    "eeprom": "EEPROM_bytes",
    "data flash memory (eeprom) (bytes)": "EEPROM_bytes",
    "data eeprom": "EEPROM_bytes",
    "eeprom (bytes) data": "EEPROM_bytes",  # PIC18 unreversed form
    "data eeprom memory (bytes)": "EEPROM_bytes",
    "data flash (kb)": "Auxiliary_Flash_KB",
    "data flash": "Auxiliary_Flash_KB",
    "auxiliary flash (kb)": "Auxiliary_Flash_KB",

    # Pin info
    "pins": "Pincount",
    "pin count": "Pincount",
    "pins i/o": "IO_Pins_Max",  # PIC18 form
    "i/o pins": "IO_Pins_Max",
    "max. frequency (mhz)": "CPU_Speed_Max_MHz",
    "maximum cpu frequency": "CPU_Speed_Max_MHz",
    "max frequency (mhz)": "CPU_Speed_Max_MHz",
    "general purpose i/o": "IO_Pins_Max",
    "general purpose i/o(2)": "IO_Pins_Max",
    "i/o pins (up to)": "IO_Pins_Max",
    "gpio": "IO_Pins_Max",
    "gpios": "IO_Pins_Max",
    "i/o srport pins(1)/ pins": "IO_Pins_Max",  # PIC16F format: takes "12/8" -> need to parse

    # Combined fields (need split parsing)
    "cmp/cmp(lp)": "PIC_CMP_CMPLP",  # PIC16F: "1/1" = 1 normal + 1 LP = 2 total
    ")pl(pmc/pmc": "PIC_CMP_CMPLP",  # reversed

    # Comms peripherals
    "twi/i2c": "I2C",
    "twi/i2c(1)": "I2C",
    "i2c": "I2C",
    "spi": "SPI",
    "usart": "USART",
    "uart": "USART",
    "u(s)art": "USART",
    "i2c/spi": "I2C_SPI_combined",  # PIC16F lists "I2C/SPI: 2/2" — needs parsing
    "eusart": "USART",
    "trasue": "USART",  # reversed EUSART
    "usart/spi host": "USART_SPI_host",  # AVR EB
    "spi host/client": "SPI",  # AVR EB
    "lin-usart/irda®": "USART",  # PIC24
    "lin-usart/irda": "USART",
    "spi width variable": "SPI",  # PIC24 'SPI htdiW elbairaV' (Variable Width SPI)
    "variable width spi": "SPI",

    # Analog
    "10-bit adc (channels)": "ADC_Channels",
    "12-bit adc": "ADC_Channels",
    "12-bit adc channels (external+/external-/internal)": "ADC_Channels",
    "12-bit differential adc (channels)": "ADC_Channels",
    "analog comparator (ac)": "Number_of_Comparators",
    "analog comparators (ac)": "Number_of_Comparators",
    "ac": "Number_of_Comparators",
    "comparator": "Number_of_Comparators",
    "comparators": "Number_of_Comparators",  # PIC18/PIC24 plural
    "cmp": "Number_of_Comparators",
    "pmc": "Number_of_Comparators",  # reversed CMP
    "digital-to-analog converter (dac) channels": "Number_of_DACs",
    "10-bit dac": "DAC_Outputs",
    "8-bit dac": "DAC_Outputs",
    "operational amplifier": "Number_of_Op_Amps",
    "refiilpma lanoitarepo": "Number_of_Op_Amps",  # reversed (whole string)
    "refiilpma operational": "Number_of_Op_Amps",  # PDF transposition — observed form
    "amplifier operational": "Number_of_Op_Amps",  # if word order swapped
    "operational refiilpma": "Number_of_Op_Amps",
    "operational amplifier (op)": "Number_of_Op_Amps",
    "srefiilpma po": "Number_of_Op_Amps",  # dsPIC33AK reversed: "Op Amplifiers"
    "po srefiilpma": "Number_of_Op_Amps",
    "op srefiilpma": "Number_of_Op_Amps",
    "op amplifiers": "Number_of_Op_Amps",
    "op amps": "Number_of_Op_Amps",
    "op amp": "Number_of_Op_Amps",
    "ptc": "PTC_Channels",
    "peripheral touch controller (ptc)": "Hardware_Touch",
    "general purpose i/o pins (input/output(2))": "IO_Pins_Max",  # AVR EB

    # Timers
    "16-bit timer/counter type a (tca)": "TCA_count",
    "16-bit timer/counter type b (tcb)": "TCB_count",
    "16-bit timer/counter type e (tce)": "TCE_count",
    "16-bit timer/counter type f (tcf)": "TCF_count",
    "12-bit timer/counter type d (tcd)": "TCD_count",
    "waveform extension (wex)": "WEX_count",
    "tc": "TC_count",
    "tcc": "TCC_count",
    "real-time counter (rtc)": "Hardware_RTC",
    "rtc": "Hardware_RTC",
    "rtcc": "Hardware_RTC",  # PIC24
    "16-bit timers": "Timers_16bit",
    "timers 16-bit": "Timers_16bit",  # PIC18/PIC24 unreversed form
    "timers 16-bit": "Timers_16bit",

    # Other peripherals
    "configurable custom logic look-up table (ccl lut)": "CCL_LUTs",
    "ccl lut": "CCL_LUTs",
    "clc": "CCL_LUTs",
    "watchdog timer": "WDT",
    "watchdog timer (wdt)": "WDT",
    "wdt": "WDT",
    "windowed watchdog timer": "Windowed_WDT",
    "event system (evsys) channels": "Event_System_Channels",
    "event system channels": "Event_System_Channels",
    "usb 2.0 full-speed device": "USB_Modules",
    "can-fd instances": "CAN_CANFD",

    # PIC-specific
    "16-bit pwm/ ccp": "PIC_PWM_CCP",  # parse "2/2"
    "/mwp pcc tib-61": "PIC_PWM_CCP",  # reversed: "16-Bit CCP/PWM"
    "pwm ccp/10-bit": "PIC_PWM_CCP",  # PIC18 unreversed: "10-bit CCP/PWM"
    "10-bit ccp/pwm": "PIC_PWM_CCP",
    "ic/oc/pwm": "PWM_outputs",  # PIC24
    "6-output/2-output mccp": "Motor_Control_PWM_PIC",  # PIC24 "1/3" = 1 6-output + 3 2-output
    "ccp": "CCP",
    "8-bit timers with hlt/ 16-bit timers(2)": "PIC_8b_16b_timers",  # parse "3/2"
    "external interrupt pins": "External_Interrupts",
    "interrupt-on-change pins": "IOC_Pins",
    # PIC24 ADC
    "10/12-bit a/d channels": "ADC_Channels",
    "12/10-bit a/d channels": "ADC_Channels",
    "channels d/a 10/12-bit": "ADC_Channels",  # PIC24 unreversed merged form
    "channels a/d 10/12-bit": "ADC_Channels",
    "channels amd": "DMA_Channels",  # PIC24 unreversed: "DMA Channels"
    "dma channels": "DMA_Channels",
    "channels dma": "DMA_Channels",
    "channels ctmu": "CTMU_Channels",  # PIC24
    "ctmu channels": "CTMU_Channels",
    "umtc": "CTMU_Channels",  # dsPIC reversed CTMU
    # dsPIC ADC channel headers (observed in failure cases)
    "inputs adc": "ADC_Channels",
    "adc inputs": "ADC_Channels",
    "channels adc": "ADC_Channels",
    "adc channels": "ADC_Channels",
    "channels) (external adc 12-bit": "ADC_Channels",  # dsPIC33CK
    "12-bit adc (external channels)": "ADC_Channels",
    "inputs) golana (external adcs": "ADC_Channels",  # dsPIC33AK partially-reversed "Analog Inputs"
    "external adcs analog inputs": "ADC_Channels",
    "external adc inputs": "ADC_Channels",
    # dsPIC DAC headers (observed)
    "dacs 12-bit": "Number_of_DACs",
    "12-bit dacs": "Number_of_DACs",
    "dacs with comparators": "Number_of_DACs",  # dsPIC33AK
    "outputs dac": "DAC_Outputs",
    "dac outputs": "DAC_Outputs",
    # dsPIC-specific
    "(kbyte) flash program": "Program_Memory_KB",  # dsPIC reversed )etybK( merged
    ")etybk( flash program": "Program_Memory_KB",  # partial-reversed observed
    "(kbytes) ram": "RAM_KB",
    "(kbytes) sram": "RAM_KB",
    "ram (kbytes)": "RAM_KB",
    "ram kbytes": "RAM_KB",
    ")setybk( ram": "RAM_KB",  # partially reversed
    "timer(1,2) 16-bit": "Timers_16bit",
    "16-bit timer(1,2)": "Timers_16bit",
    "input cap": "Input_Capture",  # dsPIC30 — split column
    "erutpac input": "Input_Capture",
    "input erutpac": "Input_Capture",
    "output comp/std pwm": "Output_Compare_PWM",  # dsPIC30
    "erapmoc output": "Output_Compare",
    "output erapmoc": "Output_Compare",
    "uart": "USART",
    "trau": "USART",  # reversed
    "external interrupts": "External_Interrupts",
    "external interrupts(3)": "External_Interrupts",
    "interrupts(3) external": "External_Interrupts",
    "external interrupts(3)": "External_Interrupts",
    "motor control pwm": "Motor_Control_PWM",
    "pwm control motor": "Motor_Control_PWM",  # partially reversed
    "pwm faults": "PWM_Faults",
    "faults pwm": "PWM_Faults",  # reversed
    "10-bit, 1.1 msps adc": "ADC_Channels",
    "adc 10-bit, 1.1 msps": "ADC_Channels",
    "adc msps 1.1 10-bit,": "ADC_Channels",  # partial reversed
    "rappameer pins": "Remappable_Pins",  # dsPIC reversed
    "remappable pins": "Remappable_Pins",
    "pins remappable": "Remappable_Pins",
    "pins elbappameer": "Remappable_Pins",
    "remappable peripherals": "Remappable_Pins",
    "i2c": "I2C",  # already there but ensure post-trademark-strip works
    "input capture": "Input_Capture",
    "output compare": "Output_Compare",

    # Package
    "package": "Packages",
    "packages": "Packages",
}


def _norm_key(k):
    """Normalize a raw key for lookup."""
    if not k:
        return ""
    k = str(k).lower().strip()
    # Collapse whitespace and newlines
    k = re.sub(r"\s+", " ", k).strip()
    # Strip trademark/registered symbols that often appear in dsPIC headers (I2C™, IrDA®)
    k = k.replace("™", "").replace("®", "").strip()
    return k


def _parse_size_kb(value, key_says_kb=False, key_says_bytes=False):
    """Parse strings like '16 KB', '7K', '512' (bytes), '2 KB', '1024' to KB number.

    key_says_kb: when the source header explicitly named the unit as KB
        (e.g. 'Flash (KB)'), so a bare number like '256' is 256 KB, not 256 bytes.
    key_says_bytes: when the header explicitly named the unit as bytes
        (e.g. 'Program Memory (bytes)'), so a bare number like '32768' is bytes
        and should be divided.
    """
    if not value:
        return ""
    v = str(value).strip()

    # Slash forms: '256+3' (main + boot Flash) — return the first number
    m = re.match(r"(\d+(?:\.\d+)?)\s*[+]\s*\d+", v)
    if m:
        n = float(m.group(1))
        return str(int(n) if n == int(n) else round(n, 2))

    # If value has explicit unit, use it
    m = re.search(r"(\d+(?:\.\d+)?)\s*(KB|K)\b", v, re.IGNORECASE)
    if m:
        n = float(m.group(1))
        return str(int(n) if n == int(n) else round(n, 2))

    # Plain number — interpretation depends on key context
    m = re.match(r"(\d+(?:\.\d+)?)$", v)
    if m:
        n = float(m.group(1))
        if key_says_kb:
            return str(int(n) if n == int(n) else round(n, 2))
        if key_says_bytes:
            kb = n / 1024
            return str(int(kb) if kb == int(kb) else round(kb, 2))
        # No hint: heuristic
        if n >= 256:
            kb = n / 1024
            return str(int(kb) if kb == int(kb) else round(kb, 2))
        return str(int(n) if n == int(n) else n)
    return v


def _parse_aux_from_program(raw_value):
    """If a 'Program Memory' value is in form 'X+Y' (X main + Y boot), return Y as Aux Flash."""
    if not raw_value:
        return None
    m = re.match(r"\d+\s*[+]\s*(\d+)", str(raw_value).strip())
    if m:
        return m.group(1)
    return None


def _parse_int_first(value):
    """Extract the first integer in the string, e.g., '1 (5)' -> '5' (parens override),
    or '8 regions' -> '8'."""
    if not value:
        return ""
    v = str(value).strip()
    if v in ("-", "—", "Yes", "No", "N/A"):
        return v
    # Parens have channel count: '1 (5)' means 1 ADC with 5 channels
    m = re.search(r"\((\d+)\)", v)
    if m:
        return m.group(1)
    m = re.search(r"(\d+)", v)
    if m:
        return m.group(1)
    return v


def vectorize(pdf_path, target_part, max_pages=20):
    """
    Main entry point: extract structured parametric data for `target_part` from `pdf_path`.
    Returns dict with canonical field names.
    """
    # Stage 1+2: Tables
    raw, sources = table_extractor.extract_all_for_part(pdf_path, target_part, max_pages=max_pages)

    # Stage 3: Features section regex parsing
    features = features_parser.parse_features(pdf_path, max_pages=8, target_part=target_part)

    result = {
        "part": target_part,
        "pdf": str(pdf_path),
        "sources": sources,
        "fields": {},
        "raw": raw,
        "features": features,
    }

    fields = result["fields"]

    for raw_key, raw_val in raw.items():
        key_norm = _norm_key(raw_key)
        canonicals = RAW_TO_CANONICAL_MULTI.get(key_norm)
        if canonicals is None:
            single = RAW_TO_CANONICAL.get(key_norm)
            canonicals = [single] if single else None

        if canonicals is None:
            # Try partial match — strip parentheticals
            stripped = re.sub(r"\s*\([^)]*\)\s*", "", key_norm).strip()
            canonicals = RAW_TO_CANONICAL_MULTI.get(stripped)
            if canonicals is None:
                single = RAW_TO_CANONICAL.get(stripped)
                canonicals = [single] if single else None

        if canonicals is None:
            # Fuzzy: contains-based matching for common variants
            fuzzy = None
            if "program" in key_norm and "flash" in key_norm:
                fuzzy = "Program_Memory_KB"
            elif "flash memory" in key_norm:
                fuzzy = "Program_Memory_KB"
            elif "data" in key_norm and "sram" in key_norm:
                fuzzy = "RAM_KB"
            elif key_norm.startswith("sram"):
                fuzzy = "RAM_KB"
            elif ("data flash" in key_norm or "eeprom" in key_norm) and "memory" in key_norm:
                fuzzy = "EEPROM_bytes"
            elif "i/o" in key_norm and "pin" in key_norm and "(1)" in key_norm:
                fuzzy = "IO_Pins_Max"
            elif "operational" in key_norm and "amp" in key_norm:
                fuzzy = "Number_of_Op_Amps"
            elif key_norm == "refiilpma lanoitarepo":
                fuzzy = "Number_of_Op_Amps"
            elif "external interrupt" in key_norm:
                fuzzy = "External_Interrupts"
            elif "windowed watchdog" in key_norm:
                fuzzy = "Windowed_WDT"
            elif "12-bit" in key_norm and "adc" in key_norm and "modules" not in key_norm:
                fuzzy = "ADC_Channels"
            elif "modules adc" in key_norm or "adc modules" in key_norm:
                fuzzy = "ADC_Modules"
            elif ("pwm" in key_norm or "mwp" in key_norm) and ("ccp" in key_norm or "pcc" in key_norm):
                fuzzy = "PIC_PWM_CCP"  # both reversed and forward forms
            elif "8-bit" in key_norm and "16-bit" in key_norm and "timer" in key_norm:
                fuzzy = "PIC_8b_16b_timers"
            elif "i2c" in key_norm and "spi" in key_norm and "/" in key_norm:
                fuzzy = "I2C_SPI_combined"
            canonicals = [fuzzy] if fuzzy else None

        if not canonicals:
            continue

        raw_value = (raw_val or "").strip()
        if not raw_value:
            continue

        # A dash / underscore in a count-style cell means "none of these for this variant".
        # We use it later (per-canonical) to set 0 for count fields, so they outrank
        # features-bullet defaults. For non-count fields we just skip.
        is_dash = raw_value in ("-", "—", "_", "–")

        # Hints from the source key about the unit
        key_says_kb = bool(re.search(r"\(\s*K\s*B?\s*\)|\bK\s*B?\b", str(raw_key), re.IGNORECASE)) and \
                      not re.search(r"\(\s*BYTES?\s*\)", str(raw_key), re.IGNORECASE)
        key_says_bytes = bool(re.search(r"\(\s*BYTES?\s*\)|\bBYTES?\b", str(raw_key), re.IGNORECASE))

        # If the Program-Memory value is in 'X+Y' form, capture Y as Aux Flash.
        if any(c == "Program_Memory_KB" for c in canonicals if c):
            aux = _parse_aux_from_program(raw_value)
            if aux:
                fields.setdefault("Auxiliary_Flash_KB", aux)

        for canonical in canonicals:
            if canonical is None:
                continue
            value = raw_value
            # Apply value parsers per canonical
            if canonical in ("Program_Memory_KB", "RAM_KB", "Auxiliary_Flash_KB"):
                value = _parse_size_kb(value, key_says_kb=key_says_kb, key_says_bytes=key_says_bytes)
            elif canonical == "EEPROM_bytes":
                value = re.sub(r"\s*B\b", "", value).strip()
            elif canonical in ("ADC_Channels", "Number_of_Comparators", "Number_of_DACs",
                               "Number_of_Op_Amps", "TCA_count", "TCB_count", "TCD_count",
                               "TCE_count", "TCF_count", "WEX_count",
                               "TC_count", "TCC_count", "CCL_LUTs", "Event_System_Channels",
                               "USB_Modules", "I2C", "SPI", "USART", "CCP",
                               "External_Interrupts", "IOC_Pins", "DAC_Outputs",
                               "Timers_16bit", "DMA_Channels", "CTMU_Channels"):
                if is_dash:
                    value = "0"  # explicit absence in the table for THIS variant
                else:
                    value = _parse_int_first(value)
            elif is_dash:
                continue  # non-count field with a dash — skip
            elif canonical == "PWM_outputs":
                # PIC24 IC/OC/PWM "3/3" means 3 IC + 3 OC + 3 PWM modules — take the last
                if "/" in str(value):
                    parts = [p.strip() for p in str(value).split("/")]
                    try:
                        value = parts[-1]
                        int(value)  # validate
                    except (ValueError, TypeError):
                        value = _parse_int_first(value)
                else:
                    value = _parse_int_first(value)
            elif canonical == "IO_Pins_Max":
                m = re.match(r"(\d+)", str(value))
                if m:
                    value = m.group(1)
            elif canonical == "Pincount":
                m = re.search(r"(\d+)", str(value))
                if m:
                    value = m.group(1)

            if canonical not in fields or not fields[canonical]:
                fields[canonical] = value

    # Compute derived fields — sum AVR-style 16-bit timer counts (TCA, TCB, TCE)
    # NOTE: TCF (Timer/Counter type F) is 24-bit despite the table label, so excluded.
    timer_keys_16 = ("TCA_count", "TCB_count", "TCE_count")
    if any(k in fields for k in timer_keys_16):
        try:
            t16 = sum(int(fields.get(k, "0") or "0") for k in timer_keys_16)
            if t16 > 0:
                fields["Timers_16bit"] = str(t16)
        except (ValueError, TypeError):
            pass

    # SAM-family TC count is 16-bit
    if "TC_count" in fields and "Timers_16bit" not in fields:
        fields["Timers_16bit"] = fields["TC_count"]

    # PTC channels presence -> Hardware_Touch = PTC
    if "PTC_Channels" in fields and fields["PTC_Channels"]:
        fields["Hardware_Touch"] = "PTC"
        # Clean ptc channel value - just the number
        m = re.search(r"(\d+)", fields["PTC_Channels"])
        if m:
            fields["PTC_Channels"] = m.group(1)

    # PIC PWM/CCP "X/Y" — X is dedicated PWM modules, Y is CCP modules.
    # PWM_outputs total depends on family interpretation:
    # - PIC16F175xx (no dedicated PWM in 24/25/26 variants, has 4 in 74/75/76 variants):
    #     For 24/25/26 (PWM=2): 2 PWM + 2 CCP = 4 outputs
    #     For 74/75/76 (PWM=4): 4 PWM (CCPs not counted as PWM here) = 4
    # - PIC16F181xx and 171xx: same pattern (4 dedicated PWM, 2 CCP, total = 4)
    # Heuristic: if dedicated PWM count >= 4, that's the PWM_outputs (CCPs separate).
    # Otherwise, sum PWM+CCP.
    pic_pwm = fields.pop("PIC_PWM_CCP", None)
    if pic_pwm and "/" in pic_pwm:
        parts = pic_pwm.split("/")
        if len(parts) == 2:
            try:
                pwm = int(parts[0].strip())
                ccp = int(parts[1].strip())
                fields.setdefault("CCP", str(ccp))
                # If 4+ dedicated PWMs, those are the answer
                if pwm >= 4:
                    fields.setdefault("PWM_outputs", str(pwm))
                else:
                    fields.setdefault("PWM_outputs", str(pwm + ccp))
            except (ValueError, TypeError):
                fields.setdefault("PWM_outputs", parts[0].strip())
                fields.setdefault("CCP", parts[1].strip())

    # PIC 8-bit/16-bit timers "3/2"
    pic_timers = fields.pop("PIC_8b_16b_timers", None)
    if pic_timers and "/" in pic_timers:
        parts = pic_timers.split("/")
        if len(parts) == 2:
            fields.setdefault("Timers_8bit", parts[0].strip())
            fields.setdefault("Timers_16bit", parts[1].strip())

    # PIC I2C/SPI "2/2"
    pic_i2c_spi = fields.pop("I2C_SPI_combined", None)
    if pic_i2c_spi and "/" in pic_i2c_spi:
        parts = pic_i2c_spi.split("/")
        if len(parts) == 2:
            fields.setdefault("I2C", parts[0].strip())
            fields.setdefault("SPI", parts[1].strip())

    # AVR EB combo "USART/SPI host": this is a USART (which CAN act as SPI host),
    # not a separate SPI peripheral. Count it as USART only — the dedicated
    # "SPI host/client" already counts as SPI.
    usart_spi = fields.pop("USART_SPI_host", None)
    if usart_spi:
        try:
            n = int(usart_spi)
            fields.setdefault("USART", str(n))
        except (ValueError, TypeError):
            fields.setdefault("USART", usart_spi)

    # PIC CMP/CMPLP "1/1" -> sum to 2 total comparators
    pic_cmp = fields.pop("PIC_CMP_CMPLP", None)
    if pic_cmp and "/" in pic_cmp:
        parts = pic_cmp.split("/")
        if len(parts) == 2:
            try:
                total = int(parts[0].strip()) + int(parts[1].strip())
                fields["Number_of_Comparators"] = str(total)
            except (ValueError, TypeError):
                pass

    # Derive PWM_outputs from TC count for SAM/PIC32CM families: each TC has 2 outputs
    if "PWM_outputs" not in fields and "TC_count" in fields:
        try:
            tc = int(fields["TC_count"])
            fields["PWM_outputs"] = str(tc * 2)
        except (ValueError, TypeError):
            pass

    # AVR EB has WEX (Waveform Extension) — that's their motor control PWM.
    # WEX provides 4 motor-control-style outputs (high+low pairs from TCE channels).
    wex = fields.pop("WEX_count", None)
    if wex:
        try:
            n = int(wex)
            if n > 0:
                # WEX adds 4 motor control outputs per instance (per TCE compare channel pair)
                fields.setdefault("Motor_Control_PWM", "4")
        except (ValueError, TypeError):
            pass

    # AVR EB: TCE has 4 outputs + WEX (Waveform Extension) provides 4 more = 8 PWM outputs
    if "PWM_outputs" not in fields and target_part:
        target_upper = target_part.upper()
        if target_upper.startswith(("AVR16EB", "AVR32EB", "AVR64EB")):
            # AVR EB has TCE with 4 channels + WEX = 8 PWM outputs
            fields["PWM_outputs"] = "8"
        elif target_upper.startswith(("AVR16DU", "AVR32DU", "AVR64DU",
                                      "AVR16SD", "AVR32SD", "AVR64SD")):
            # AVR DU/SD has TCA with 3 channels = 3 PWM outputs (no WEX on DU)
            if target_upper.startswith(("AVR16SD", "AVR32SD", "AVR64SD")):
                fields["PWM_outputs"] = "3"  # SD has TCD optimization but TCA still 3
            else:
                fields["PWM_outputs"] = "3"

    # Merge in features-extracted fields (don't overwrite existing)
    for k, v in features.items():
        if v and (k not in fields or not fields[k]):
            fields[k] = v

    # Family-specific defaults
    target_upper = target_part.upper() if target_part else ""
    if target_upper.startswith(("PIC16F17", "PIC16F18")):
        # PIC16F1xxxx: CVD via ADC2, no hardware RTC
        fields.setdefault("Hardware_Touch", "CVD")
        fields.setdefault("Hardware_RTC", "No")
    elif target_upper.startswith(("AVR", "ATTINY", "ATMEGA")) and not target_upper.startswith("AVR16EB") and not target_upper.startswith("AVR32EB") and not target_upper.startswith("AVR64EB"):
        # Most modern AVR families have RTC, no PTC except specific ones
        fields.setdefault("Hardware_RTC", "Yes")
    elif target_upper.startswith(("PIC32CM", "ATSAM")):
        fields.setdefault("Hardware_RTC", "Yes")
        # PIC32CM/SAM typically have no EEPROM
        fields.setdefault("EEPROM_bytes", "0")
        # Pincount->IO map for SAM/PIC32CM (these are the standard mappings)
        if "IO_Pins_Max" not in fields and "Pincount" in fields:
            sam_io_map = {"32": "26", "48": "38", "64": "52", "100": "84"}
            if str(fields["Pincount"]) in sam_io_map:
                fields["IO_Pins_Max"] = sam_io_map[str(fields["Pincount"])]
        # PIC32CM GV does not have CCL (the LE/MC families do)
        if target_upper.startswith("PIC32CM") and "GV" in target_upper:
            fields.setdefault("CCL_LUTs", "0")

    # Derive Pincount from I/O pins for PIC16F families when not in table
    if "Pincount" not in fields and "IO_Pins_Max" in fields:
        try:
            io = int(fields["IO_Pins_Max"])
            # Common PIC16F mapping: I/O pins -> total pin count
            io_to_pins = {
                6: 8, 11: 14, 12: 14, 13: 14, 18: 20, 24: 28, 25: 28, 35: 40, 36: 40,
                # AVR DU/EB
                9: 14, 14: 20, 15: 20, 17: 28, 21: 28, 23: 28, 24: 28, 27: 32,
                # ARM SAM/PIC32CM
                26: 32, 38: 48, 52: 64, 80: 100, 84: 100,
            }
            if io in io_to_pins:
                fields["Pincount"] = str(io_to_pins[io])
        except (ValueError, TypeError):
            pass

    # NOTE: For PIC16F1xxxx parts with 36 I/O pins (suffix 74/75/76), they support
    # BOTH 40-pin PDIP and 44-pin TQFP packages. We default to 40 (already set by
    # io_to_pins map). If you need 44-pin specifically, check Packages field.

    # Defaults for fields almost always present but rarely mentioned in tables.
    # If we extracted any data at all, assume these defaults.
    if fields:
        # Aux Flash defaults to 0 unless explicitly stated otherwise
        fields.setdefault("Auxiliary_Flash_KB", "0")
        # If WDT keyword found, normalize to "Yes"
        if "WDT" in fields:
            v = str(fields["WDT"]).strip()
            if v in ("1", "Y", "Yes", "yes"):
                fields["WDT"] = "Yes"
        # If Hardware_RTC found via raw, normalize
        if "Hardware_RTC" in fields:
            v = str(fields["Hardware_RTC"]).strip()
            if v in ("1", "Y", "Yes", "yes"):
                fields["Hardware_RTC"] = "Yes"
            elif v in ("0", "N", "No", "no", "-", "—"):
                fields["Hardware_RTC"] = "No"

        # Common defaults: if peripheral keyword wasn't found, default to 0
        # (only for families we know well)
        for f in ("Number_of_Op_Amps", "Number_of_DACs", "DAC_Outputs",
                  "Quadrature_Encoder", "Motor_Control_PWM"):
            fields.setdefault(f, "0")

    return result


if __name__ == "__main__":
    import sys
    pdf = sys.argv[1] if len(sys.argv) > 1 else "PIC32CMGV_datasheet.pdf"
    target = sys.argv[2] if len(sys.argv) > 2 else "PIC32CM3204GV00048"

    result = vectorize(pdf, target)
    print(f"Part: {result['part']}")
    print(f"PDF: {result['pdf']}")
    print(f"Sources: {result['sources']}")
    print(f"\nExtracted fields ({len(result['fields'])}):")
    for k, v in sorted(result['fields'].items()):
        print(f"  {k:<30} {v}")
    print(f"\nRaw fields ({len(result['raw'])}):")
    for k, v in result['raw'].items():
        print(f"  {k!r}: {v!r}")
