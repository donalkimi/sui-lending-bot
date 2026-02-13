#!/usr/bin/env python3
"""
Auto-populate coingecko_id field in token_registry by matching contract addresses.

Fetches all coins from CoinGecko API and matches Sui platform contract addresses
with token_contract values in the database.

Usage:
    python utils/populate_coingecko_ids.py           # Update all missing IDs
    python utils/populate_coingecko_ids.py --force   # Update all IDs (overwrite existing)
    python utils/populate_coingecko_ids.py --dry-run # Show matches without updating
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


def fetch_coingecko_coin_list() -> list:
    """
    Fetch all coins with platform data from CoinGecko.

    Returns:
        List of coin dictionaries with id, symbol, name, and platforms
    """
    import requests

    url = "https://api.coingecko.com/api/v3/coins/list"
    params = {'include_platform': 'true'}

    try:
        print("[INFO] Fetching coin list from CoinGecko API...")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        coins = response.json()
        print(f"[SUCCESS] Fetched {len(coins)} coins from CoinGecko")

        return coins

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch CoinGecko coin list: {e}")
        return []


def build_contract_to_id_mapping(coins: list) -> Dict[str, Tuple[str, str, str]]:
    """
    Build mapping from Sui contract addresses to CoinGecko IDs.

    Args:
        coins: List of coin dictionaries from CoinGecko API

    Returns:
        Dict mapping contract address to (coingecko_id, symbol, name)
    """
    mapping = {}
    sui_coins = 0

    for coin in coins:
        if 'platforms' in coin and isinstance(coin['platforms'], dict):
            if 'sui' in coin['platforms']:
                contract = coin['platforms']['sui']
                coingecko_id = coin['id']
                symbol = coin.get('symbol', 'UNKNOWN')
                name = coin.get('name', 'Unknown')

                # Store mapping
                mapping[contract] = (coingecko_id, symbol, name)
                sui_coins += 1

    print(f"[INFO] Found {sui_coins} coins on Sui platform")

    return mapping


def normalize_contract_address(contract: str) -> str:
    """
    Normalize contract address for matching.

    Some addresses might have slight variations in formatting.
    This function can be extended to handle variations.

    Args:
        contract: Contract address string

    Returns:
        Normalized contract address
    """
    # For now, just return as-is
    # Could add lowercasing, trimming, etc. if needed
    return contract.strip()


def update_token_registry(
    mapping: Dict[str, Tuple[str, str, str]],
    force: bool = False,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    Update coingecko_id field in token_registry for matched contracts.

    Args:
        mapping: Dict mapping contract address to (coingecko_id, symbol, name)
        force: If True, update all tokens (overwrite existing IDs)
        dry_run: If True, show matches without updating database

    Returns:
        Dict with counts: {'total': int, 'matched': int, 'updated': int, 'skipped': int}
    """
    engine = get_db_engine()

    # Query tokens from database
    if force:
        query = "SELECT token_contract, symbol FROM token_registry WHERE symbol IS NOT NULL ORDER BY symbol"
    else:
        query = "SELECT token_contract, symbol FROM token_registry WHERE symbol IS NOT NULL AND coingecko_id IS NULL ORDER BY symbol"

    df = pd.read_sql_query(query, engine)

    if df.empty:
        print("[INFO] No tokens to update")
        return {'total': 0, 'matched': 0, 'updated': 0, 'skipped': 0}

    print(f"[INFO] Processing {len(df)} tokens from token_registry...")

    total = len(df)
    matched = 0
    updated = 0
    skipped = 0

    matches = []

    for idx, row in df.iterrows():
        token_contract = row['token_contract']
        db_symbol = row['symbol']

        # Normalize contract for matching
        normalized_contract = normalize_contract_address(token_contract)

        # Check if we have a match
        if normalized_contract in mapping:
            coingecko_id, cg_symbol, cg_name = mapping[normalized_contract]
            matched += 1

            matches.append({
                'token_contract': token_contract,
                'db_symbol': db_symbol,
                'coingecko_id': coingecko_id,
                'cg_symbol': cg_symbol,
                'cg_name': cg_name
            })

            print(f"[MATCH] {db_symbol:8s} -> {coingecko_id:20s} ({cg_name})")

            if not dry_run:
                # Update database
                try:
                    update_query = text("""
                    UPDATE token_registry
                    SET coingecko_id = :coingecko_id
                    WHERE token_contract = :token_contract
                    """)

                    with engine.connect() as conn:
                        conn.execute(update_query, {
                            'coingecko_id': coingecko_id,
                            'token_contract': token_contract
                        })
                        conn.commit()

                    updated += 1

                except Exception as e:
                    print(f"[ERROR] Failed to update {db_symbol}: {e}")
                    skipped += 1
        else:
            # No match found
            print(f"[NO MATCH] {db_symbol:8s} ({token_contract[:40]}...)")
            skipped += 1

    print("\n" + "="*80)
    print(f"[SUMMARY]")
    print(f"  Total tokens:   {total}")
    print(f"  Matched:        {matched}")
    if not dry_run:
        print(f"  Updated:        {updated}")
    print(f"  Skipped:        {skipped}")
    print("="*80)

    if dry_run:
        print("\n[DRY RUN] No changes were made to the database")
        print(f"Run without --dry-run to apply {matched} updates")

    return {
        'total': total,
        'matched': matched,
        'updated': updated if not dry_run else 0,
        'skipped': skipped
    }


def verify_updates():
    """Verify that coingecko_ids were updated successfully."""
    engine = get_db_engine()

    query = """
    SELECT symbol, coingecko_id, token_contract
    FROM token_registry
    WHERE coingecko_id IS NOT NULL
    ORDER BY symbol
    """

    df = pd.read_sql_query(query, engine)

    if df.empty:
        print("\n[WARNING] No tokens with coingecko_id found")
        return

    print(f"\n[VERIFICATION] {len(df)} tokens with CoinGecko IDs:")
    print("="*80)
    print(f"{'Symbol':<10} {'CoinGecko ID':<25} {'Contract':<40}")
    print("-"*80)

    for _, row in df.iterrows():
        contract_short = row['token_contract'][:40] + "..." if len(row['token_contract']) > 40 else row['token_contract']
        print(f"{row['symbol']:<10} {row['coingecko_id']:<25} {contract_short}")

    print("="*80)


def populate_coingecko_ids_auto(engine=None, dry_run=False, force=False):
    """
    Auto-populate coingecko_id for tokens in token_registry.

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
    # (it calls get_db_engine() internally, so we need to make it use our engine)
    import dashboard.db_utils as db_utils
    original_get_engine = db_utils.get_db_engine
    db_utils.get_db_engine = lambda: engine

    try:
        # Fetch coin list from CoinGecko
        coins = fetch_coingecko_coin_list()

        if not coins:
            return 0

        # Build contract -> ID mapping
        mapping = build_contract_to_id_mapping(coins)

        if not mapping:
            return 0

        # Update token registry
        results = update_token_registry(mapping, force=force, dry_run=dry_run)

        return results.get('updated', 0) if not dry_run else results.get('matched', 0)

    except Exception as e:
        print(f"[ERROR] populate_coingecko_ids_auto failed: {e}")
        return 0

    finally:
        # Restore original get_db_engine function
        db_utils.get_db_engine = original_get_engine


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Auto-populate coingecko_id field in token_registry'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Update all tokens (overwrite existing coingecko_ids)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show matches without updating database'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Only verify current coingecko_id population (no updates)'
    )

    args = parser.parse_args()

    # If verify mode, just show current state
    if args.verify:
        verify_updates()
        sys.exit(0)

    # Fetch coin list from CoinGecko
    coins = fetch_coingecko_coin_list()

    if not coins:
        print("[ERROR] Failed to fetch coin list. Exiting.")
        sys.exit(1)

    # Build contract -> ID mapping
    mapping = build_contract_to_id_mapping(coins)

    if not mapping:
        print("[WARNING] No Sui tokens found in CoinGecko data")
        sys.exit(1)

    # Update token registry
    results = update_token_registry(mapping, force=args.force, dry_run=args.dry_run)

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