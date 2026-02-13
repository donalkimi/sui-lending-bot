#!/usr/bin/env python3
"""
Auto-populate pyth_id field in token_registry by matching contract addresses and symbols.

Fetches all Pyth price feeds from Hermes API and matches using two-step approach:
1. Primary: Contract address matching (when contract_id field is present with "sui: " prefix)
2. Secondary: Symbol matching (fallback when no contract_id available)

Usage:
    python utils/populate_pyth_ids.py           # Update all missing IDs
    python utils/populate_pyth_ids.py --force   # Update all IDs (overwrite existing)
    python utils/populate_pyth_ids.py --dry-run # Show matches without updating
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Tuple
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.db_utils import get_db_engine
from sqlalchemy import text
import pandas as pd


def fetch_pyth_price_feeds() -> list:
    """
    Fetch all Pyth price feeds from Hermes API.

    Returns:
        List of price feed dictionaries with id and attributes
    """
    import requests

    url = "https://hermes.pyth.network/v2/price_feeds"
    params = {'asset_type': 'crypto'}

    try:
        print("[INFO] Fetching price feeds from Pyth Hermes API...")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        feeds = response.json()
        print(f"[SUCCESS] Fetched {len(feeds)} price feeds from Pyth")

        return feeds

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch Pyth price feeds: {e}")
        return []


def build_pyth_id_mappings(feeds: list) -> Tuple[Dict[str, Tuple[str, str]], Dict[str, Tuple[str, str]]]:
    """
    Build two mappings: contract-based and symbol-based.

    Args:
        feeds: List of price feed dictionaries from Pyth API

    Returns:
        tuple: (contract_mapping, symbol_mapping)
        - contract_mapping: {contract_address: (pyth_id, symbol)}
        - symbol_mapping: {symbol: (pyth_id, description)}
    """
    contract_mapping = {}
    symbol_mapping = {}
    sui_contracts = 0

    for feed in feeds:
        pyth_id = feed['id']
        attrs = feed.get('attributes', {})
        base_symbol = attrs.get('base', '')

        # Contract-based mapping (primary)
        if 'contract_id' in attrs and attrs['contract_id']:
            contract_id = attrs['contract_id']
            if contract_id.startswith('sui: '):
                # Extract contract address after "sui: " prefix
                contract_address = contract_id[5:].strip()
                contract_mapping[contract_address] = (pyth_id, base_symbol)
                sui_contracts += 1

        # Symbol-based mapping (secondary fallback)
        if base_symbol:
            symbol_mapping[base_symbol] = (pyth_id, attrs.get('description', ''))

    print(f"[INFO] Found {sui_contracts} feeds with Sui contract addresses")
    print(f"[INFO] Found {len(symbol_mapping)} feeds with symbols")

    return contract_mapping, symbol_mapping


def match_tokens_to_pyth_ids(
    contract_mapping: Dict[str, Tuple[str, str]],
    symbol_mapping: Dict[str, Tuple[str, str]]
) -> Dict[str, Tuple[str, str, str]]:
    """
    Match tokens from token_registry to Pyth IDs.

    Priority:
    1. Contract address match
    2. Symbol match

    Args:
        contract_mapping: Dict mapping contract address to (pyth_id, symbol)
        symbol_mapping: Dict mapping symbol to (pyth_id, description)

    Returns:
        dict: {token_contract: (pyth_id, match_type, matched_value)}
    """
    engine = get_db_engine()

    query = """
    SELECT token_contract, symbol
    FROM token_registry
    WHERE symbol IS NOT NULL
    ORDER BY symbol
    """

    df = pd.read_sql_query(query, engine)

    matches = {}
    contract_matches = 0
    symbol_matches = 0

    for _, row in df.iterrows():
        token_contract = row['token_contract']
        symbol = row['symbol']

        # Priority 1: Contract address match
        if token_contract in contract_mapping:
            pyth_id, matched_symbol = contract_mapping[token_contract]
            matches[token_contract] = (pyth_id, 'contract', token_contract)
            contract_matches += 1
        # Priority 2: Symbol match
        elif symbol in symbol_mapping:
            pyth_id, description = symbol_mapping[symbol]
            matches[token_contract] = (pyth_id, 'symbol', symbol)
            symbol_matches += 1

    print(f"[INFO] Matched {len(matches)} tokens total:")
    print(f"  - {contract_matches} via contract address")
    print(f"  - {symbol_matches} via symbol")

    return matches


def update_token_registry(
    matches: Dict[str, Tuple[str, str, str]],
    force: bool = False,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    Update pyth_id field in token_registry for matched tokens.

    Args:
        matches: Dict mapping token_contract to (pyth_id, match_type, matched_value)
        force: If True, update all tokens (overwrite existing IDs)
        dry_run: If True, show matches without updating database

    Returns:
        Dict with counts: {'total': int, 'matched': int, 'updated': int, 'skipped': int}
    """
    engine = get_db_engine()

    # Query tokens from database
    if force:
        query = "SELECT token_contract, symbol, pyth_id FROM token_registry WHERE symbol IS NOT NULL ORDER BY symbol"
    else:
        query = "SELECT token_contract, symbol, pyth_id FROM token_registry WHERE symbol IS NOT NULL AND pyth_id IS NULL ORDER BY symbol"

    df = pd.read_sql_query(query, engine)

    if df.empty:
        print("[INFO] No tokens to update")
        return {'total': 0, 'matched': 0, 'updated': 0, 'skipped': 0}

    print(f"[INFO] Processing {len(df)} tokens from token_registry...")

    total = len(df)
    updated = 0
    skipped = 0

    print("\n" + "="*100)
    print(f"{'Symbol':<10} {'Match Type':<12} {'Matched Value':<30} {'Pyth ID (first 16 chars)':<20}")
    print("-"*100)

    for idx, row in df.iterrows():
        token_contract = row['token_contract']
        db_symbol = row['symbol']

        # Check if we have a match
        if token_contract in matches:
            pyth_id, match_type, matched_value = matches[token_contract]

            # Show match info
            pyth_id_short = pyth_id[:16] + "..."
            matched_value_display = matched_value[:30] if len(matched_value) > 30 else matched_value
            print(f"{db_symbol:<10} {match_type:<12} {matched_value_display:<30} {pyth_id_short:<20}")

            if not dry_run:
                # Update database
                try:
                    update_query = text("""
                    UPDATE token_registry
                    SET pyth_id = :pyth_id
                    WHERE token_contract = :token_contract
                    """)

                    with engine.connect() as conn:
                        conn.execute(update_query, {
                            'pyth_id': pyth_id,
                            'token_contract': token_contract
                        })
                        conn.commit()

                    updated += 1

                except Exception as e:
                    print(f"[ERROR] Failed to update {db_symbol}: {e}")
                    skipped += 1
        else:
            skipped += 1

    print("="*100)
    print(f"\n[SUMMARY]")
    print(f"  Total tokens:   {total}")
    print(f"  Matched:        {len(matches)}")
    if not dry_run:
        print(f"  Updated:        {updated}")
    print(f"  Skipped:        {skipped}")
    print("="*100)

    if dry_run:
        print(f"\n[DRY RUN] No changes were made to the database")
        print(f"Run without --dry-run to apply {len(matches)} updates")

    return {
        'total': total,
        'matched': len(matches),
        'updated': updated if not dry_run else 0,
        'skipped': skipped
    }


def verify_updates():
    """Verify that pyth_ids were updated successfully."""
    engine = get_db_engine()

    query = """
    SELECT symbol, pyth_id, token_contract
    FROM token_registry
    WHERE pyth_id IS NOT NULL
    ORDER BY symbol
    """

    df = pd.read_sql_query(query, engine)

    if df.empty:
        print("\n[WARNING] No tokens with pyth_id found")
        return

    print(f"\n[VERIFICATION] {len(df)} tokens with Pyth IDs:")
    print("="*100)
    print(f"{'Symbol':<10} {'Pyth ID (first 16 chars)':<25} {'Contract (first 40 chars)':<40}")
    print("-"*100)

    for _, row in df.iterrows():
        pyth_id_short = row['pyth_id'][:16] + "..." if len(row['pyth_id']) > 16 else row['pyth_id']
        contract_short = row['token_contract'][:40] + "..." if len(row['token_contract']) > 40 else row['token_contract']
        print(f"{row['symbol']:<10} {pyth_id_short:<25} {contract_short}")

    print("="*100)


def populate_pyth_ids_auto(engine=None, dry_run=False, force=False):
    """
    Auto-populate pyth_id for tokens in token_registry.

    This is a library function that can be called from other modules (e.g., refresh_pipeline).

    Args:
        engine: Optional SQLAlchemy engine. If None, will create one via get_db_engine()
        dry_run: If True, show matches without updating database
        force: If True, update all tokens (overwrite existing IDs)

    Returns:
        int: Number of newly matched/updated tokens (0 if error or no matches)
    """
    # Use provided engine or create one
    if engine is None:
        from dashboard.db_utils import get_db_engine as _get_db_engine
        engine = _get_db_engine()

    # Store original engine in module globals for update_token_registry to use
    import dashboard.db_utils as db_utils
    original_get_engine = db_utils.get_db_engine
    db_utils.get_db_engine = lambda: engine

    try:
        # Fetch price feeds from Pyth
        feeds = fetch_pyth_price_feeds()

        if not feeds:
            return 0

        # Build mappings
        contract_mapping, symbol_mapping = build_pyth_id_mappings(feeds)

        if not contract_mapping and not symbol_mapping:
            return 0

        # Match tokens to Pyth IDs
        matches = match_tokens_to_pyth_ids(contract_mapping, symbol_mapping)

        if not matches:
            return 0

        # Update token registry
        results = update_token_registry(matches, force=force, dry_run=dry_run)

        return results.get('updated', 0) if not dry_run else results.get('matched', 0)

    except Exception as e:
        print(f"[ERROR] populate_pyth_ids_auto failed: {e}")
        return 0

    finally:
        # Restore original get_db_engine function
        db_utils.get_db_engine = original_get_engine


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Auto-populate pyth_id field in token_registry'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Update all tokens (overwrite existing pyth_ids)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show matches without updating database'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Only verify current pyth_id population (no updates)'
    )

    args = parser.parse_args()

    # If verify mode, just show current state
    if args.verify:
        verify_updates()
        sys.exit(0)

    # Fetch price feeds from Pyth
    feeds = fetch_pyth_price_feeds()

    if not feeds:
        print("[ERROR] Failed to fetch price feeds. Exiting.")
        sys.exit(1)

    # Build mappings
    contract_mapping, symbol_mapping = build_pyth_id_mappings(feeds)

    if not contract_mapping and not symbol_mapping:
        print("[WARNING] No mappings found in Pyth data")
        sys.exit(1)

    # Match tokens to Pyth IDs
    matches = match_tokens_to_pyth_ids(contract_mapping, symbol_mapping)

    if not matches:
        print("[WARNING] No matches found")
        sys.exit(1)

    # Update token registry
    results = update_token_registry(matches, force=args.force, dry_run=args.dry_run)

    # Verify if updates were made
    if not args.dry_run and results['updated'] > 0:
        time.sleep(1)  # Brief pause before verification
        verify_updates()

    # Exit with appropriate code
    if results['matched'] == 0:
        sys.exit(1)  # No matches found
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
