"""
Download all datasheet PDFs into ./datasheets/ given family_datasheets.json.
Skips files already present. Uses a polite per-domain delay.
"""
import json
import os
import re
import time
import urllib.request
import urllib.error


DATASHEETS_DIR = "datasheets"
DELAY_SEC = 1.0  # politeness gap
USER_AGENT = "Mozilla/5.0 (datasheet-vectorizer; cliffordswartz1@gmail.com)"


def safe_filename(url):
    """Get a safe local filename from a Microchip datasheet URL."""
    # Last path component
    name = url.rsplit("/", 1)[-1]
    # Strip query/fragment if any sneaked through
    name = name.split("?")[0].split("#")[0]
    # Sanitize
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if not name.endswith(".pdf"):
        name += ".pdf"
    return name


def download(url, dest, retries=2):
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://www.microchip.com/",
                "Accept": "application/pdf,*/*",
            })
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if len(data) < 1024:
                raise ValueError(f"Suspiciously small file: {len(data)} bytes")
            if not data.startswith(b"%PDF"):
                raise ValueError(f"Not a PDF: starts with {data[:10]!r}")
            with open(dest, "wb") as f:
                f.write(data)
            return
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(3)
    raise last_err


def main():
    os.makedirs(DATASHEETS_DIR, exist_ok=True)

    fams = json.load(open("family_datasheets.json", encoding="utf-8-sig"))
    # Build set of unique URLs (multiple families may share a datasheet)
    url_to_families = {}
    for fkey, info in fams.items():
        url = info.get("datasheet_url")
        if not url:
            continue
        url_to_families.setdefault(url, []).append(fkey)

    print(f"Total families: {len(fams)}")
    print(f"Families with URL: {sum(1 for f in fams.values() if f.get('datasheet_url'))}")
    print(f"Unique PDFs to download: {len(url_to_families)}")
    print()

    ok = skipped = failed = 0
    failures = []
    for i, (url, fkeys) in enumerate(url_to_families.items(), 1):
        fname = safe_filename(url)
        dest = os.path.join(DATASHEETS_DIR, fname)
        if os.path.exists(dest) and os.path.getsize(dest) > 1024:
            skipped += 1
            continue
        try:
            print(f"[{i}/{len(url_to_families)}] Downloading {fname}  (used by {len(fkeys)} family/-ies)")
            download(url, dest)
            ok += 1
            time.sleep(DELAY_SEC)
        except Exception as e:
            failed += 1
            failures.append((url, str(e)))
            print(f"  FAIL: {e}")

    print()
    print(f"Done. ok={ok} skipped={skipped} failed={failed}")
    if failures:
        print("Failures:")
        for url, err in failures:
            print(f"  {url}  -> {err}")


if __name__ == "__main__":
    main()
