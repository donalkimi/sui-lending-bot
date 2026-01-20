#!/usr/bin/env python3
"""
Helper script to fetch token metadata from the token_registry database.
Used by suilend_reader-sdk.mjs to avoid making RPC calls for metadata.
"""
import sys
import json
import sqlite3
from pathlib import Path

def get_token_metadata(coin_types):
    """
    Query token_registry database for metadata of given coin types.

    Args:
        coin_types: List of coin type strings (e.g., "0x2::sui::SUI")

    Returns:
        Dictionary mapping coin_type to metadata object
    """
    # Database path relative to this script
    db_path = Path(__file__).parent.parent.parent / "data" / "lending_rates.db"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    metadata_map = {}
    for coin_type in coin_types:
        cursor.execute(
            'SELECT symbol FROM token_registry WHERE token_contract = ?',
            (coin_type,)
        )
        row = cursor.fetchone()

        if row:
            # Build metadata object matching SDK expected format
            metadata_map[coin_type] = {
                'symbol': row[0],
                'name': row[0],  # Use symbol as name
                'iconUrl': None,
                'description': None
            }
        else:
            # Fallback: extract symbol from coin type string
            # e.g., "0x...::sui::SUI" → "SUI"
            parts = coin_type.split("::")
            symbol = parts[-1] if len(parts) > 0 else coin_type

            metadata_map[coin_type] = {
                'symbol': symbol,
                'name': symbol,
                'iconUrl': None,
                'description': None
            }

    conn.close()
    return metadata_map


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: get_token_metadata.py '<json_array_of_coin_types>'"}))
        sys.exit(1)

    try:
        # Parse JSON array of coin types from command line
        coin_types = json.loads(sys.argv[1])

        # Get metadata from database
        metadata_map = get_token_metadata(coin_types)

        # Output as JSON
        print(json.dumps(metadata_map))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
