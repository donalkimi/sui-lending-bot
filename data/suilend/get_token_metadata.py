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
        Dictionary with two keys:
        - 'metadata': mapping coin_type to metadata object
        - 'missing_decimals': list of tokens with NULL decimals
    """
    # Database path relative to this script
    db_path = Path(__file__).parent.parent.parent / "data" / "lending_rates.db"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    metadata_map = {}
    missing_decimals = []

    for coin_type in coin_types:
        cursor.execute(
            'SELECT symbol, decimals FROM token_registry WHERE token_contract = ?',
            (coin_type,)
        )
        row = cursor.fetchone()

        if row:
            symbol, decimals = row

            # FAIL LOUDLY: If decimals is NULL, track this token
            if decimals is None:
                missing_decimals.append({
                    'coin_type': coin_type,
                    'symbol': symbol,
                    'error': 'decimals is NULL in token_registry'
                })
                # Don't add to metadata_map - this will cause SDK to skip this token
                continue

            # Build metadata object matching SDK expected format
            metadata_map[coin_type] = {
                'symbol': symbol,
                'name': symbol,  # Use symbol as name
                'decimals': decimals,  # Now required from database
                'iconUrl': None,
                'description': None
            }
        else:
            # Token not in registry at all
            parts = coin_type.split("::")
            symbol = parts[-1] if len(parts) > 0 else coin_type

            missing_decimals.append({
                'coin_type': coin_type,
                'symbol': symbol,
                'error': 'token not found in token_registry'
            })
            # Don't add to metadata_map - this will cause SDK to skip this token

    conn.close()
    return {
        'metadata': metadata_map,
        'missing_decimals': missing_decimals
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: get_token_metadata.py '<json_array_of_coin_types>'"}))
        sys.exit(1)

    try:
        # Parse JSON array of coin types from command line
        coin_types = json.loads(sys.argv[1])

        # Get metadata from database
        result = get_token_metadata(coin_types)

        # Output as JSON (returns both metadata and missing_decimals)
        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
