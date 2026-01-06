#!/usr/bin/env python3
"""
Fetch Suilend Main Pool reserve data via Node SDK and save to CSV.
"""

import json
import subprocess
import csv
from pathlib import Path

NODE_SCRIPT = "suilend_reader-sdk.mjs"
OUTPUT_CSV = "suilend_reserves.csv"

def fetch_reserves():
    """Call the Node.js script and return parsed JSON."""
    result = subprocess.run(
        ["node", NODE_SCRIPT],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("Error running Node script:")
        print(result.stderr)
        return []
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print("Error parsing JSON output:", e)
        return []

def format_number(val):
    """Format numeric values with 3 decimal places."""
    try:
        return f"{float(val):,.3f}"
    except (TypeError, ValueError):
        return val

def save_to_csv(reserves, filename=OUTPUT_CSV):
    """Save reserves data to CSV with formatted numbers."""
    headers = [
        "Reserve ID", "Token Symbol", "Token Contract",
        "Lend APR Base", "Lend APR Total", "Lend APR Reward",
        "Borrow APR Base", "Borrow APR Total", "Borrow APR Reward",
        "Total Supplied", "Total Borrowed", "Utilisation"
    ]

    path = Path(filename)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in reserves:
            row = [
                r.get("reserve_id"),
                r.get("token_symbol"),
                r.get("token_contract"),
                format_number(r.get("lend_apr_base")),
                format_number(r.get("lend_apr_total")),
                format_number(r.get("lend_apr_reward")),
                format_number(r.get("borrow_apr_base")),
                format_number(r.get("borrow_apr_total")),
                format_number(r.get("borrow_apr_reward")),
                format_number(r.get("total_supplied")),
                format_number(r.get("total_borrowed")),
                format_number(r.get("utilisation"))
            ]
            writer.writerow(row)
    print(f"Saved {len(reserves)} reserves to {filename}")

def main():
    reserves = fetch_reserves()
    if not reserves:
        print("No reserve data found.")
        return
    save_to_csv(reserves)

if __name__ == "__main__":
    main()
