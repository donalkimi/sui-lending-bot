#!/usr/bin/env python3
"""
Helper script to fetch token metadata from the token_registry database.
Used by suilend_reader-sdk.mjs to avoid making RPC calls for metadata.

Supports both SQLite (local dev) and Supabase PostgreSQL (production on Railway).
"""
import sys
import json
from pathlib import Path

# Add project root to path to import settings
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config import settings

def get_db_connection():
    """Get database connection (SQLite or PostgreSQL based on settings)"""
    if settings.USE_CLOUD_DB:
        import psycopg2
        return psycopg2.connect(settings.SUPABASE_URL)
    else:
        import sqlite3
        return sqlite3.connect(settings.SQLITE_PATH)

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
    conn = get_db_connection()
    cursor = conn.cursor()

    # Use correct placeholder for database type
    placeholder = '%s' if settings.USE_CLOUD_DB else '?'

    metadata_map = {}
    missing_decimals = []

    print(f"[get_token_metadata] Querying {len(coin_types)} tokens from token_registry (USE_CLOUD_DB={settings.USE_CLOUD_DB})", file=sys.stderr)

    for coin_type in coin_types:
        print(f"[get_token_metadata] Checking token: {coin_type}", file=sys.stderr)
        cursor.execute(
            f'SELECT symbol, decimals FROM token_registry WHERE token_contract = {placeholder}',
            (coin_type,)
        )
        row = cursor.fetchone()

        if row:
            symbol, decimals = row
            print(f"[get_token_metadata] Found: {symbol} with decimals={decimals}", file=sys.stderr)

            # FAIL LOUDLY: If decimals is NULL, track this token
            if decimals is None:
                print(f"[get_token_metadata] ERROR: {symbol} ({coin_type}) has NULL decimals!", file=sys.stderr)
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
            print(f"[get_token_metadata] ERROR: Token {coin_type} not found in token_registry!", file=sys.stderr)

            missing_decimals.append({
                'coin_type': coin_type,
                'symbol': symbol,
                'error': 'token not found in token_registry'
            })
            # Don't add to metadata_map - this will cause SDK to skip this token

    conn.close()

    print(f"[get_token_metadata] Summary: {len(metadata_map)} tokens found, {len(missing_decimals)} missing", file=sys.stderr)
    if missing_decimals:
        print(f"[get_token_metadata] Missing tokens: {[m['symbol'] for m in missing_decimals]}", file=sys.stderr)

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
