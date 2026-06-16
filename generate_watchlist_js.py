#!/usr/bin/env python3
"""Regenerate docs/watchlist.js from watchlist.csv.

Run this whenever you edit watchlist.csv so the web calculator stays in sync:

    python3 generate_watchlist_js.py
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "watchlist.csv")
OUT_PATH = os.path.join(HERE, "docs", "watchlist.js")


def main() -> None:
    rows = []
    with open(CSV_PATH, newline="") as f:
        for row in csv.DictReader(f):
            rows.append({k: v.strip() for k, v in row.items()})

    with open(OUT_PATH, "w") as out:
        out.write("// Auto-generated from watchlist.csv - the 100-name AI universe.\n")
        out.write("// To update: edit watchlist.csv and rerun generate_watchlist_js.py.\n")
        out.write("window.WATCHLIST = " + json.dumps(rows, indent=2) + ";\n")

    print(f"Wrote {len(rows)} tickers to {OUT_PATH}")


if __name__ == "__main__":
    main()
