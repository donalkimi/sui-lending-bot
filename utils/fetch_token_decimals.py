#!/usr/bin/env python3
"""
Utility script to fetch token decimals from Sui blockchain.

This script can be used to:
1. Fetch decimals for a single token contract
2. Fetch decimals for all tokens in database missing decimals
3. Update token_registry with fetched decimals

Usage:
    # Fetch decimals for a specific token
    python3 data/fetch_token_decimals.py 0x2::sui::SUI

    # Fetch decimals for all tokens missing decimals in database
    python3 data/fetch_token_decimals.py --all

    # Dry run (show what would be updated without committing)
    python3 data/fetch_token_decimals.py --all --dry-run
"""

import sqlite3
import json
import subprocess
import sys
import argparse
from pathlib import Path
from typing import Dict, Optional, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Database path
DB_PATH = project_root / "data" / "lending_rates.db"

# RPC URL (configurable via environment or settings)
try:
    from config.settings import SUI_RPC_URL
except ImportError:
    SUI_RPC_URL = "https://rpc.mainnet.sui.io"


def fetch_decimals_from_chain(coin_type: str) -> Optional[int]:
    """
    Fetch token decimals from Sui blockchain using getCoinMetadata.

    Args:
        coin_type: Full coin type (e.g., "0x2::sui::SUI")

    Returns:
        Decimals as integer, or None if fetch failed
    """
    script = f'''
import {{ SuiClient }} from "@mysten/sui/client";

const client = new SuiClient({{ url: "{SUI_RPC_URL}" }});

async function fetchMetadata() {{
    try {{
        const metadata = await client.getCoinMetadata({{ coinType: "{coin_type}" }});
        console.log(JSON.stringify(metadata));
    }} catch (err) {{
        console.error(JSON.stringify({{ error: err.message }}));
        process.exit(1);
    }}
}}

fetchMetadata();
'''

    try:
        result = subprocess.run(
            ["node", "--input-type=module"],
            input=script,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_root / "data" / "suilend")  # Run in suilend directory for node_modules
        )

        if result.returncode != 0:
            return None

        metadata = json.loads(result.stdout)
        return metadata.get("decimals")

    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return None


def get_tokens_missing_decimals(conn: sqlite3.Connection) -> List[tuple]:
    """
    Get all tokens from database that are missing decimals.

    Args:
        conn: Database connection

    Returns:
        List of tuples (token_contract, symbol)
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT token_contract, symbol
        FROM token_registry
        WHERE decimals IS NULL
        ORDER BY symbol
    """)
    return cursor.fetchall()


def update_token_decimals(conn: sqlite3.Connection, coin_type: str, decimals: int) -> None:
    """
    Update token_registry with decimals for a specific token.

    Args:
        conn: Database connection
        coin_type: Token contract address
        decimals: Token decimal precision
    """
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE token_registry
        SET decimals = ?
        WHERE token_contract = ?
    """, (decimals, coin_type))


def main():
    parser = argparse.ArgumentParser(
        description="Fetch token decimals from Sui blockchain and update database"
    )
    parser.add_argument(
        "token",
        nargs="?",
        help="Token contract address (e.g., 0x2::sui::SUI). If omitted, use --all"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Fetch decimals for all tokens missing decimals in database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without committing changes"
    )

    args = parser.parse_args()

    if not args.token and not args.all:
        parser.error("Must specify either a token contract or --all")
        return 1

    print("="*80)
    print("[Fetch Decimals] Token Decimals Fetcher")
    print("="*80)
    print(f"[Config] Database: {DB_PATH}")
    print(f"[Config] RPC URL: {SUI_RPC_URL}")
    if args.dry_run:
        print("[Config] Mode: DRY RUN (no changes will be committed)")
    print()

    conn = sqlite3.connect(str(DB_PATH))

    try:
        if args.token:
            # Single token mode
            coin_type = args.token
            print(f"[Fetch] Querying Sui chain for: {coin_type}")

            decimals = fetch_decimals_from_chain(coin_type)

            if decimals is None:
                print(f"[ERROR] Failed to fetch decimals from chain")
                return 1

            print(f"[Result] Decimals: {decimals}")

            if not args.dry_run:
                update_token_decimals(conn, coin_type, decimals)
                conn.commit()
                print(f"[Success] Updated database")
            else:
                print(f"[Dry Run] Would update database with decimals={decimals}")

        else:
            # All tokens mode
            tokens = get_tokens_missing_decimals(conn)

            if not tokens:
                print("[Info] All tokens already have decimals. Nothing to do.")
                return 0

            print(f"[Fetch] Found {len(tokens)} tokens missing decimals")
            print()

            success_count = 0
            failed_tokens = []

            for i, (coin_type, symbol) in enumerate(tokens, 1):
                symbol_display = symbol if symbol else coin_type.split("::")[-1]
                print(f"[{i}/{len(tokens)}] {symbol_display[:20]}... ({coin_type[:40]}...)")

                decimals = fetch_decimals_from_chain(coin_type)

                if decimals is None:
                    print(f"  [SKIP] Failed to fetch from chain")
                    failed_tokens.append({"symbol": symbol_display, "contract": coin_type})
                    continue

                print(f"  [OK] decimals={decimals}")

                if not args.dry_run:
                    update_token_decimals(conn, coin_type, decimals)

                success_count += 1

            if not args.dry_run:
                conn.commit()

            print()
            print("="*80)
            print(f"[Complete] Results:")
            print(f"  - Success: {success_count}/{len(tokens)} tokens")
            print(f"  - Failed: {len(failed_tokens)} tokens")

            if failed_tokens:
                print()
                print("[Failed Tokens]")
                for token in failed_tokens:
                    print(f"  - {token['symbol']}: {token['contract']}")

            if args.dry_run:
                print()
                print("[Dry Run] No changes committed to database")
            else:
                print()
                print("[Success] Database updated")

            print("="*80)

        return 0

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
