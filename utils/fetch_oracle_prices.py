#!/usr/bin/env python3
"""
Fetch oracle prices from CoinGecko and Pyth APIs.

This utility fetches real-time prices from multiple oracle sources and updates
the oracle_prices table. Only valid prices overwrite existing data.

Usage:
    # Fetch prices for all tokens with oracle IDs
    python utils/fetch_oracle_prices.py --all

    # Fetch price for specific token
    python utils/fetch_oracle_prices.py --token 0x2::sui::SUI

    # Dry run (show what would be updated without committing)
    python utils/fetch_oracle_prices.py --all --dry-run
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.db_utils import get_db_engine
from dashboard.oracle_price_utils import compute_latest_price
from sqlalchemy import text
import pandas as pd


def fetch_coingecko_prices_batch(coingecko_ids: list) -> dict:
    """
    Fetch multiple prices from CoinGecko API in a single request.

    Args:
        coingecko_ids: List of CoinGecko token IDs (e.g., ['sui', 'usd-coin'])

    Returns:
        Dict mapping coingecko_id to (price_usd, timestamp) or empty dict if failed
    """
    if not coingecko_ids:
        return {}

    try:
        import requests

        # CoinGecko API supports comma-separated IDs (max 250)
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': ','.join(coingecko_ids),
            'vs_currencies': 'usd'
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        timestamp = datetime.now()

        # Build result dict
        results = {}
        for cg_id in coingecko_ids:
            if cg_id in data and 'usd' in data[cg_id]:
                price = float(data[cg_id]['usd'])
                results[cg_id] = (price, timestamp)

        return results

    except Exception as e:
        print(f"[ERROR] CoinGecko batch fetch failed: {e}")
        return {}


def fetch_coingecko_price(coingecko_id: str) -> Optional[Tuple[float, datetime]]:
    """
    Fetch price from CoinGecko API (single token).

    Args:
        coingecko_id: CoinGecko token ID (e.g., 'sui', 'usd-coin')

    Returns:
        Tuple of (price_usd, timestamp) or None if failed
    """
    if not coingecko_id:
        return None

    try:
        import requests

        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': coingecko_id,
            'vs_currencies': 'usd'
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if coingecko_id in data and 'usd' in data[coingecko_id]:
            price = float(data[coingecko_id]['usd'])
            timestamp = datetime.now()
            return price, timestamp

        return None

    except Exception as e:
        print(f"[ERROR] CoinGecko fetch failed for {coingecko_id}: {e}")
        return None


def fetch_pyth_price(pyth_id: str) -> Optional[Tuple[float, datetime]]:
    """
    Fetch price from Pyth Network API.

    Args:
        pyth_id: Pyth price feed ID (hex string)

    Returns:
        Tuple of (price_usd, timestamp) or None if failed
    """
    if not pyth_id:
        return None

    try:
        import requests

        # Pyth Hermes API endpoint
        url = "https://hermes.pyth.network/api/latest_price_feeds"
        params = {
            'ids[]': pyth_id
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data and len(data) > 0:
            feed = data[0]
            price_data = feed.get('price', {})

            # Pyth returns price with exponent
            price = float(price_data.get('price', 0))
            expo = int(price_data.get('expo', 0))
            publish_time = int(price_data.get('publish_time', 0))

            adjusted_price = price * (10 ** expo)
            timestamp = datetime.fromtimestamp(publish_time)

            return adjusted_price, timestamp

        return None

    except Exception as e:
        print(f"[ERROR] Pyth fetch failed for {pyth_id[:16]}...: {e}")
        return None


def fetch_pyth_prices_batch(pyth_ids: list) -> dict:
    """
    Fetch multiple prices from Pyth in a single request.

    Args:
        pyth_ids: List of Pyth price feed IDs (hex strings)

    Returns:
        Dict mapping pyth_id to (price_usd, timestamp) or empty dict if failed
    """
    if not pyth_ids:
        return {}

    try:
        import requests

        # Pyth supports multiple ids[] parameters in a single request
        url = "https://hermes.pyth.network/api/latest_price_feeds"
        params = [('ids[]', pyth_id) for pyth_id in pyth_ids]

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        results = {}
        for feed in data:
            pyth_id = feed['id']
            price_data = feed.get('price', {})

            # Pyth returns price with exponent
            price = float(price_data.get('price', 0))
            expo = int(price_data.get('expo', 0))
            publish_time = int(price_data.get('publish_time', 0))

            adjusted_price = price * (10 ** expo)
            feed_timestamp = datetime.fromtimestamp(publish_time)

            results[pyth_id] = (adjusted_price, feed_timestamp)

        return results

    except Exception as e:
        print(f"[ERROR] Pyth batch fetch failed: {e}")
        return {}


def fetch_defillama_prices_batch(token_contracts: list) -> dict:
    """
    Fetch multiple prices from DeFi Llama in a single request.

    Args:
        token_contracts: List of Sui contract addresses (e.g., '0x2::sui::SUI')

    Returns:
        Dict mapping token_contract to (price_usd, timestamp, confidence) or empty dict if failed
    """
    if not token_contracts:
        return {}

    try:
        import requests

        # Build comma-separated coin identifiers with "sui:" prefix
        coin_ids = [f"sui:{contract}" for contract in token_contracts]
        coins_param = ','.join(coin_ids)

        # DeFi Llama API endpoint
        url = f"https://coins.llama.fi/prices/current/{coins_param}"

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        data = response.json()

        if 'coins' not in data:
            print(f"[WARNING] DeFi Llama response missing 'coins' field")
            return {}

        results = {}
        for contract in token_contracts:
            coin_key = f"sui:{contract}"
            if coin_key in data['coins']:
                coin_data = data['coins'][coin_key]

                price = float(coin_data.get('price', 0))
                timestamp_unix = int(coin_data.get('timestamp', 0))
                confidence = coin_data.get('confidence', None)

                # Convert Unix timestamp to datetime
                timestamp = datetime.fromtimestamp(timestamp_unix)

                # Store tuple: (price, timestamp, confidence)
                results[contract] = (price, timestamp, confidence)

        return results

    except Exception as e:
        print(f"[ERROR] DeFi Llama batch fetch failed: {e}")
        return {}


def update_oracle_price(
    token_contract: str,
    symbol: str,
    coingecko_price: Optional[float],
    coingecko_time: Optional[datetime],
    pyth_price: Optional[float],
    pyth_time: Optional[datetime],
    defillama_price: Optional[float],
    defillama_time: Optional[datetime],
    defillama_confidence: Optional[float],
    dry_run: bool = False
) -> bool:
    """
    Update oracle_prices table with new price data.
    Only overwrites if valid price returned (None values are ignored).

    Args:
        token_contract: Token contract address
        symbol: Token symbol
        coingecko_price: CoinGecko price (or None to keep existing)
        coingecko_time: CoinGecko timestamp (or None to keep existing)
        pyth_price: Pyth price (or None to keep existing)
        pyth_time: Pyth timestamp (or None to keep existing)
        dry_run: If True, only print what would be updated

    Returns:
        True if update succeeded, False otherwise
    """
    # Compute latest price across all oracles
    latest_price, latest_oracle, latest_time = compute_latest_price(
        coingecko_price, coingecko_time, pyth_price, pyth_time,
        defillama_price, defillama_time
    )

    if dry_run:
        print(f"[DRY RUN] Would update {symbol} ({token_contract[:16]}...):")
        if coingecko_price:
            print(f"  CoinGecko: ${coingecko_price:.6f} at {coingecko_time}")
        if pyth_price:
            print(f"  Pyth: ${pyth_price:.6f} at {pyth_time}")
        if latest_price:
            print(f"  Latest: ${latest_price:.6f} from {latest_oracle} at {latest_time}")
        return True

    try:
        engine = get_db_engine()

        # Prepare parameters for UPSERT
        params = {
            'token_contract': token_contract,
            'symbol': symbol,
            'coingecko': coingecko_price,
            'coingecko_time': coingecko_time,
            'pyth': pyth_price,
            'pyth_time': pyth_time,
            'defillama': defillama_price,
            'defillama_time': defillama_time,
            'defillama_confidence': defillama_confidence,
            'latest_price': latest_price,
            'latest_oracle': latest_oracle,
            'latest_time': latest_time,
            'last_updated': datetime.now()
        }

        # Use UPSERT to insert new rows or update existing ones
        # Only update fields that have non-None values
        query = text("""
        INSERT INTO oracle_prices (
            token_contract, symbol,
            coingecko, coingecko_time,
            pyth, pyth_time,
            defillama, defillama_time, defillama_confidence,
            latest_price, latest_oracle, latest_time,
            last_updated
        )
        VALUES (
            :token_contract, :symbol,
            :coingecko, :coingecko_time,
            :pyth, :pyth_time,
            :defillama, :defillama_time, :defillama_confidence,
            :latest_price, :latest_oracle, :latest_time,
            :last_updated
        )
        ON CONFLICT (token_contract) DO UPDATE SET
            coingecko = CASE
                WHEN :coingecko IS NOT NULL THEN :coingecko
                ELSE oracle_prices.coingecko
            END,
            coingecko_time = CASE
                WHEN :coingecko IS NOT NULL THEN :coingecko_time
                ELSE oracle_prices.coingecko_time
            END,
            pyth = CASE
                WHEN :pyth IS NOT NULL THEN :pyth
                ELSE oracle_prices.pyth
            END,
            pyth_time = CASE
                WHEN :pyth IS NOT NULL THEN :pyth_time
                ELSE oracle_prices.pyth_time
            END,
            defillama = CASE
                WHEN :defillama IS NOT NULL THEN :defillama
                ELSE oracle_prices.defillama
            END,
            defillama_time = CASE
                WHEN :defillama IS NOT NULL THEN :defillama_time
                ELSE oracle_prices.defillama_time
            END,
            defillama_confidence = CASE
                WHEN :defillama_confidence IS NOT NULL THEN :defillama_confidence
                ELSE oracle_prices.defillama_confidence
            END,
            latest_price = CASE
                WHEN :latest_price IS NOT NULL THEN :latest_price
                ELSE oracle_prices.latest_price
            END,
            latest_oracle = CASE
                WHEN :latest_oracle IS NOT NULL THEN :latest_oracle
                ELSE oracle_prices.latest_oracle
            END,
            latest_time = CASE
                WHEN :latest_time IS NOT NULL THEN :latest_time
                ELSE oracle_prices.latest_time
            END,
            last_updated = :last_updated
        """)

        with engine.connect() as conn:
            result = conn.execute(query, params)
            conn.commit()

            if result.rowcount > 0:
                if latest_price:
                    print(f"[SUCCESS] Upserted {symbol}: latest=${latest_price:.6f} from {latest_oracle}")
                else:
                    print(f"[SUCCESS] Upserted {symbol}")
                return True
            else:
                print(f"[WARNING] Upsert failed for {symbol}")
                return False

    except Exception as e:
        print(f"[ERROR] Failed to upsert {symbol}: {e}")
        return False


def fetch_all_oracle_prices(dry_run: bool = False) -> dict:
    """
    Fetch prices from all oracles for all tokens in oracle_prices table.
    Uses batch fetching for CoinGecko to avoid rate limits.

    Args:
        dry_run: If True, only show what would be updated

    Returns:
        Dict with counts: {'total': int, 'updated': int, 'failed': int}
    """
    engine = get_db_engine()

    # Query tokens from token_registry that have oracle IDs
    query = """
    SELECT
        tr.token_contract,
        tr.symbol,
        tr.coingecko_id,
        tr.pyth_id
    FROM token_registry tr
    WHERE tr.symbol IS NOT NULL
      AND (tr.coingecko_id IS NOT NULL OR tr.pyth_id IS NOT NULL)
    ORDER BY tr.symbol
    """

    df = pd.read_sql_query(query, engine)

    if df.empty:
        print("[INFO] No tokens with oracle IDs found in token_registry")
        return {'total': 0, 'updated': 0, 'failed': 0}

    print(f"[INFO] Found {len(df)} tokens with oracle IDs")

    # Batch fetch CoinGecko prices
    coingecko_ids = []
    cg_id_to_info = {}  # Map coingecko_id -> (token_contract, symbol)

    for _, row in df.iterrows():
        if pd.notna(row['coingecko_id']):
            cg_id = row['coingecko_id']
            coingecko_ids.append(cg_id)
            cg_id_to_info[cg_id] = (row['token_contract'], row['symbol'])

    print(f"[INFO] Batch fetching {len(coingecko_ids)} CoinGecko prices...")
    coingecko_prices = fetch_coingecko_prices_batch(coingecko_ids)
    print(f"[SUCCESS] Fetched {len(coingecko_prices)} CoinGecko prices")

    # Batch fetch Pyth prices
    pyth_ids = []
    for _, row in df.iterrows():
        if pd.notna(row['pyth_id']):
            pyth_ids.append(row['pyth_id'])

    if pyth_ids:
        print(f"[INFO] Batch fetching {len(pyth_ids)} Pyth prices...")
        pyth_prices = fetch_pyth_prices_batch(pyth_ids)
        print(f"[SUCCESS] Fetched {len(pyth_prices)} Pyth prices")
    else:
        pyth_prices = {}

    # Batch fetch DeFi Llama prices
    token_contracts = df['token_contract'].tolist()
    print(f"[INFO] Batch fetching {len(token_contracts)} DeFi Llama prices...")
    defillama_prices = fetch_defillama_prices_batch(token_contracts)
    print(f"[SUCCESS] Fetched {len(defillama_prices)} DeFi Llama prices")

    # Process each token
    total = len(df)
    updated = 0
    failed = 0

    for idx, row in df.iterrows():
        token_contract = row['token_contract']
        symbol = row['symbol']
        coingecko_id = row['coingecko_id']
        pyth_id = row['pyth_id']

        print(f"\n[{idx + 1}/{total}] Processing {symbol}...")

        # Get CoinGecko price from batch results
        coingecko_result = None
        if pd.notna(coingecko_id):
            if coingecko_id in coingecko_prices:
                coingecko_result = coingecko_prices[coingecko_id]
                price, _ = coingecko_result
                print(f"  ✓ CoinGecko: ${price:.6f}")
            else:
                print(f"  ✗ CoinGecko: No price for {coingecko_id}")

        # Get Pyth price from batch results
        pyth_result = None
        if pd.notna(pyth_id):
            if pyth_id in pyth_prices:
                pyth_result = pyth_prices[pyth_id]
                price, _ = pyth_result
                print(f"  ✓ Pyth: ${price:.6f}")
            else:
                print(f"  ✗ Pyth: No price for {pyth_id[:16]}...")

        # Get DeFi Llama price from batch results
        defillama_result = None
        if token_contract in defillama_prices:
            defillama_result = defillama_prices[token_contract]
            dl_price, _, dl_confidence = defillama_result
            conf_str = f" (confidence: {dl_confidence:.2f})" if dl_confidence else ""
            print(f"  ✓ DeFi Llama: ${dl_price:.6f}{conf_str}")
        else:
            print(f"  ✗ DeFi Llama: No price for {token_contract[:20]}...")

        # Update database
        if coingecko_result or pyth_result or defillama_result:
            cg_price, cg_time = coingecko_result if coingecko_result else (None, None)
            pyth_price, pyth_time = pyth_result if pyth_result else (None, None)

            # Extract DeFi Llama data
            if defillama_result:
                dl_price, dl_time, dl_confidence = defillama_result
            else:
                dl_price, dl_time, dl_confidence = None, None, None

            success = update_oracle_price(
                token_contract, symbol,
                cg_price, cg_time,
                pyth_price, pyth_time,
                dl_price, dl_time, dl_confidence,
                dry_run=dry_run
            )

            if success:
                updated += 1
            else:
                failed += 1
        else:
            print(f"  ✗ No valid prices fetched for {symbol}")
            failed += 1

    print(f"\n[SUMMARY] Total: {total}, Updated: {updated}, Failed: {failed}")

    return {
        'total': total,
        'updated': updated,
        'failed': failed
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Fetch oracle prices and update database')
    parser.add_argument('--all', action='store_true', help='Fetch prices for all tokens')
    parser.add_argument('--token', type=str, help='Fetch price for specific token contract')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without committing')

    args = parser.parse_args()

    if args.all:
        results = fetch_all_oracle_prices(dry_run=args.dry_run)
        sys.exit(0 if results['failed'] == 0 else 1)
    elif args.token:
        print("[ERROR] Single token fetch not yet implemented")
        print("[INFO] Use --all to fetch prices for all tokens with oracle IDs")
        sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
