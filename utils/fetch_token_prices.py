#!/usr/bin/env python3
"""
Utility script to fetch token prices from rates_snapshot table.

This script queries the rates_snapshot table to find the latest price
for tokens and updates the default_price column in token_registry.

Usage:
    # Fetch price for a specific token
    python3 data/fetch_token_prices.py 0x2::sui::SUI

    # Fetch prices for all tokens missing default_price
    python3 data/fetch_token_prices.py --all

    # Dry run (show what would be updated without committing)
    python3 data/fetch_token_prices.py --all --dry-run

    # Force update even if price already exists
    python3 data/fetch_token_prices.py --all --force
"""

import sqlite3
import sys
import argparse
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Database path
DB_PATH = project_root / "data" / "lending_rates.db"


def get_latest_price_from_snapshot(conn: sqlite3.Connection, coin_type: str) -> Optional[Tuple[float, datetime]]:
    """
    Get the most recent price for a token from rates_snapshot table.

    Args:
        conn: Database connection
        coin_type: Token contract address

    Returns:
        Tuple of (price, timestamp) or None if not found
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT price_usd, timestamp
        FROM rates_snapshot
        WHERE token_contract = ?
          AND price_usd IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 1
    """, (coin_type,))

    row = cursor.fetchone()
    if row:
        return (float(row[0]), row[1])
    return None


def get_tokens_missing_price(conn: sqlite3.Connection, force: bool = False) -> List[Tuple[str, str, Optional[float]]]:
    """
    Get all tokens from database that are missing default_price.

    Args:
        conn: Database connection
        force: If True, return all tokens regardless of existing price

    Returns:
        List of tuples (token_contract, symbol, current_price)
    """
    cursor = conn.cursor()

    if force:
        cursor.execute("""
            SELECT token_contract, symbol, default_price
            FROM token_registry
            ORDER BY symbol
        """)
    else:
        cursor.execute("""
            SELECT token_contract, symbol, default_price
            FROM token_registry
            WHERE default_price IS NULL
            ORDER BY symbol
        """)

    return cursor.fetchall()


def update_token_price(conn: sqlite3.Connection, coin_type: str, price: float) -> None:
    """
    Update token_registry with default_price for a specific token.

    Args:
        conn: Database connection
        coin_type: Token contract address
        price: Token price in USD
    """
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE token_registry
        SET default_price = ?
        WHERE token_contract = ?
    """, (price, coin_type))


def get_price_history_stats(conn: sqlite3.Connection, coin_type: str) -> Optional[dict]:
    """
    Get price statistics for a token from rates_snapshot.

    Args:
        conn: Database connection
        coin_type: Token contract address

    Returns:
        Dict with price statistics or None
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COUNT(*) as count,
            MIN(price_usd) as min_price,
            MAX(price_usd) as max_price,
            AVG(price_usd) as avg_price,
            MIN(timestamp) as first_seen,
            MAX(timestamp) as last_seen
        FROM rates_snapshot
        WHERE token_contract = ?
          AND price_usd IS NOT NULL
    """, (coin_type,))

    row = cursor.fetchone()
    if row and row[0] > 0:
        return {
            "count": row[0],
            "min": float(row[1]),
            "max": float(row[2]),
            "avg": float(row[3]),
            "first_seen": row[4],
            "last_seen": row[5]
        }
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Fetch token prices from rates_snapshot and update default_price"
    )
    parser.add_argument(
        "token",
        nargs="?",
        help="Token contract address (e.g., 0x2::sui::SUI). If omitted, use --all"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Fetch prices for all tokens missing default_price"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Update all tokens, even if they already have a price"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without committing changes"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show price history statistics"
    )

    args = parser.parse_args()

    if not args.token and not args.all:
        parser.error("Must specify either a token contract or --all")
        return 1

    print("="*80)
    print("[Fetch Prices] Token Price Fetcher from rates_snapshot")
    print("="*80)
    print(f"[Config] Database: {DB_PATH}")
    if args.dry_run:
        print("[Config] Mode: DRY RUN (no changes will be committed)")
    if args.force:
        print("[Config] Force mode: Will update all tokens")
    print()

    conn = sqlite3.connect(str(DB_PATH))

    try:
        if args.token:
            # Single token mode
            coin_type = args.token
            print(f"[Fetch] Querying rates_snapshot for: {coin_type}")

            result = get_latest_price_from_snapshot(conn, coin_type)

            if result is None:
                print(f"[ERROR] No price found in rates_snapshot")

                if args.verbose:
                    print(f"[Info] Checking if token exists in database...")
                    cursor = conn.cursor()
                    cursor.execute("SELECT symbol FROM token_registry WHERE token_contract = ?", (coin_type,))
                    row = cursor.fetchone()
                    if row:
                        print(f"[Info] Token exists in registry as: {row[0]}")
                    else:
                        print(f"[Info] Token not found in registry")

                return 1

            price, timestamp = result
            print(f"[Result] Price: ${price:.6f} (as of {timestamp})")

            if args.verbose:
                stats = get_price_history_stats(conn, coin_type)
                if stats:
                    print(f"[Stats] Price history:")
                    print(f"  - Data points: {stats['count']}")
                    print(f"  - Min: ${stats['min']:.6f}")
                    print(f"  - Max: ${stats['max']:.6f}")
                    print(f"  - Avg: ${stats['avg']:.6f}")
                    print(f"  - First seen: {stats['first_seen']}")
                    print(f"  - Last seen: {stats['last_seen']}")

            if not args.dry_run:
                update_token_price(conn, coin_type, price)
                conn.commit()
                print(f"[Success] Updated database")
            else:
                print(f"[Dry Run] Would update database with price=${price:.6f}")

        else:
            # All tokens mode
            tokens = get_tokens_missing_price(conn, force=args.force)

            if not tokens:
                print("[Info] All tokens already have default_price. Nothing to do.")
                print("[Tip] Use --force to update all tokens regardless")
                return 0

            mode = "all tokens" if args.force else "tokens missing default_price"
            print(f"[Fetch] Found {len(tokens)} {mode}")
            print()

            success_count = 0
            no_price_found = []
            already_has_price = []

            for i, (coin_type, symbol, current_price) in enumerate(tokens, 1):
                symbol_display = symbol if symbol else coin_type.split("::")[-1]

                # Skip if already has price and not forcing
                if current_price is not None and not args.force:
                    already_has_price.append({"symbol": symbol_display, "contract": coin_type, "price": current_price})
                    continue

                print(f"[{i}/{len(tokens)}] {symbol_display[:20]}... ({coin_type[:40]}...)")

                result = get_latest_price_from_snapshot(conn, coin_type)

                if result is None:
                    print(f"  [SKIP] No price found in rates_snapshot")
                    no_price_found.append({"symbol": symbol_display, "contract": coin_type})
                    continue

                price, timestamp = result

                status = "UPDATE" if current_price is not None else "NEW"
                print(f"  [{status}] ${price:.6f} (as of {timestamp})")

                if not args.dry_run:
                    update_token_price(conn, coin_type, price)

                success_count += 1

            if not args.dry_run:
                conn.commit()

            print()
            print("="*80)
            print(f"[Complete] Results:")
            print(f"  - Updated: {success_count}/{len(tokens)} tokens")
            print(f"  - No price found: {len(no_price_found)} tokens")

            if already_has_price:
                print(f"  - Already had price: {len(already_has_price)} tokens (use --force to update)")

            if no_price_found:
                print()
                print("[Tokens with no price in rates_snapshot]")
                print("(These tokens have never appeared in a snapshot)")
                for token in no_price_found:
                    print(f"  - {token['symbol']}: {token['contract'][:60]}...")

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
