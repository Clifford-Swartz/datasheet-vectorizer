"""
Given families.json (part -> family) and family_datasheets.json (family -> url),
produce part_to_pdf.json: { PART: "datasheets/<filename>.pdf" } for every part
whose family has a downloaded datasheet.
"""
import json
import os
from _download_datasheets import safe_filename


def main():
    fams = json.load(open("families.json", encoding="utf-8-sig"))
    fds = json.load(open("family_datasheets.json", encoding="utf-8-sig"))

    part_to_pdf = {}
    missing_family = 0
    missing_url = 0
    missing_file = 0

    for fkey, info in fams.items():
        ds = fds.get(fkey)
        if not ds:
            missing_family += len(info["parts"])
            continue
        url = ds.get("datasheet_url")
        if not url:
            missing_url += len(info["parts"])
            continue
        fname = safe_filename(url)
        local = os.path.join("datasheets", fname)
        if not os.path.exists(local):
            missing_file += len(info["parts"])
            continue
        for p in info["parts"]:
            part_to_pdf[p] = local

    with open("part_to_pdf.json", "w") as f:
        json.dump(part_to_pdf, f, indent=2)

    print(f"Total parts mapped: {len(part_to_pdf)}")
    print(f"Missing because family had no MCP entry: {missing_family}")
    print(f"Missing because family had null URL: {missing_url}")
    print(f"Missing because PDF not downloaded yet: {missing_file}")


if __name__ == "__main__":
    main()
