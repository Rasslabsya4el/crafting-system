"""Ticket #271: download the tabs of the public "Memory Strand Testing" sheet as CSV.

Usage: python -I fetch_sheet.py RAW_DIR

Writes foul.csv ("foulborn and misc currency data"), unravel.csv ("Unravelling data"), remem.csv ("remembrance data"),
alteration_int_body.csv ("ilvl 86+ int body, orb of alteration") and alteration_str_helm.csv ("ilvl 85+ str helm, orb of
alteration") into RAW_DIR. The raw files are not kept in the repository (the sheet is the source and unravel.csv is 65 MB).
Standard library only.
"""
import sys
import urllib.request
from pathlib import Path

SHEET = "1UKTS29e1XghGTQQJBiu7TR3vrancnZxiyN3tBzj30WI"
TABS = {
    "foul.csv": 1172044153,
    "unravel.csv": 349590831,
    "remem.csv": 571335548,
    "alteration_int_body.csv": 0,
    "alteration_str_helm.csv": 301832373,
}


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, gid in TABS.items():
        url = f"https://docs.google.com/spreadsheets/d/{SHEET}/export?format=csv&gid={gid}"
        with urllib.request.urlopen(url, timeout=600) as response:
            data = response.read()
        (out / name).write_bytes(data)
        print(f"{name}: {len(data)} bytes")


if __name__ == "__main__":
    main()
