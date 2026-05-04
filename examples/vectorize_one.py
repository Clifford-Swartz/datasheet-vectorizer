"""Minimum example: vectorize one part from a datasheet PDF you have locally.

Usage:
  python examples/vectorize_one.py <path/to/datasheet.pdf> <PART_NUMBER>

Example:
  python examples/vectorize_one.py datasheets/PIC18F26-45-46-Q10-Data-Sheet-DS40001996.pdf PIC18F46Q10
"""
import json
import sys

# Make the package importable when run from anywhere
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasheet_vectorizer import vectorize


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    pdf, part = sys.argv[1], sys.argv[2]
    result = vectorize.vectorize(pdf, part, max_pages=15)
    print(f"Part:    {result['part']}")
    print(f"PDF:     {result['pdf']}")
    print(f"Sources: {result['sources']}  (page, table_index)")
    print()
    print("Extracted fields:")
    for k, v in sorted(result["fields"].items()):
        print(f"  {k:<28} = {v}")


if __name__ == "__main__":
    main()
