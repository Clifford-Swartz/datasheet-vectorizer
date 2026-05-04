"""For each held-out part, prepare a verification task: list of (field, our_value) pairs
to be checked against the actual datasheet."""
import json

holdout = json.load(open("holdout_sample.json", encoding="utf-8-sig"))
vec = json.load(open("vectorized_all.json", encoding="utf-8-sig"))

# Fields we want to verify — focus on table-driven, factual fields
FIELDS_TO_CHECK = [
    "Program_Memory_KB", "RAM_KB", "EEPROM_bytes", "Pincount", "IO_Pins_Max",
    "I2C", "SPI", "USART", "ADC_Channels", "Number_of_Comparators",
    "Number_of_Op_Amps", "Number_of_DACs", "DAC_Outputs",
    "Hardware_RTC", "WDT", "Timers_16bit", "PWM_outputs", "CCP",
    "CPU_Speed_Max_MHz", "Auxiliary_Flash_KB", "CCL_LUTs",
    "TempRange_Min", "TempRange_Max",
]

tasks = []
for entry in holdout:
    part = entry["part"]
    pdf = entry["pdf"]
    info = vec.get(part, {})
    fields = info.get("fields", {})
    items = []
    for f in FIELDS_TO_CHECK:
        v = fields.get(f, "")
        if str(v).strip():  # only verify non-empty extractions
            items.append({"field": f, "our_value": v})
    tasks.append({
        "part": part,
        "pdf": pdf,
        "items": items,
    })

with open("verification_tasks.json", "w") as f:
    json.dump(tasks, f, indent=2)

total_items = sum(len(t["items"]) for t in tasks)
print(f"{len(tasks)} parts, {total_items} field/value pairs to verify")
print(f"Avg fields/part: {total_items / len(tasks):.1f}")
