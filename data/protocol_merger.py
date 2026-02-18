"""
Protocol Data Merger

Fetches and merges data from Navi, AlphaFi, and Suilend protocols into unified DataFrames.
"""

import pandas as pd
from typing import Tuple, Set

from data.navi.navi_reader import NaviReader
from data.alphalend.alphafi_reader import AlphaFiReader, AlphaFiReaderConfig
from data.suilend.suilend_reader import SuilendReader, SuilendReaderConfig
from data.scallop_lend.scallop_lend_reader import ScallopLendReader, ScallopReaderConfig
from data.scallop_borrow.scallop_borrow_reader import ScallopBorrowReader
from data.pebble.pebble_reader import PebbleReader

# Import stablecoin configuration
try:
    from config.stablecoins import STABLECOIN_CONTRACTS
except ImportError:
    # Fallback if config doesn't exist
    STABLECOIN_CONTRACTS = set()


def normalize_coin_type(coin_type: str) -> str:
    """
    Normalize Sui coin type (remove leading zeros from address).
    
    Args:
        coin_type: Raw coin type string (e.g., "0x00002::sui::SUI")
        
    Returns:
        Normalized coin type string (e.g., "0x2::sui::SUI")
    """
    if not coin_type:
        return ""
    
    parts = str(coin_type).split("::")
    if len(parts) < 3:
        return coin_type
    
    addr = parts[0].lower()
    if addr.startswith("0x"):
        hexpart = addr[2:].lstrip("0") or "0"
        addr = "0x" + hexpart
    
    return "::".join([addr] + parts[1:])


def fetch_protocol_data(protocol_name: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Fetch data from a single protocol.

    Args:
        protocol_name: Protocol to fetch ("Navi", "AlphaFi", or "Suilend")

    Returns:
        Tuple of (lend_df, borrow_df, collateral_df)
        Returns empty DataFrames if fetch fails
    """
    try:
        if protocol_name == "Navi":
            print("\tgetting navi rates:")
            reader = NaviReader()
            return reader.get_all_data()

        elif protocol_name == "AlphaFi":
            print("\t\tgetting AlphaFi rates:")
            config = AlphaFiReaderConfig(
                node_script_path="data/alphalend/alphalend_reader-sdk.mjs"
            )
            reader = AlphaFiReader(config)
            return reader.get_all_data()

        elif protocol_name == "Suilend":
            print("\t\tgetting SuiLend rates:")
            config = SuilendReaderConfig(
                node_script_path="data/suilend/suilend_reader-sdk.mjs"
            )
            reader = SuilendReader(config)
            return reader.get_all_data()

        elif protocol_name == "ScallopLend":
            print("\t\tgetting ScallopLend rates:")
            config = ScallopReaderConfig(
                node_script_path="data/scallop_shared/scallop_reader-sdk.mjs"
            )
            reader = ScallopLendReader(config)
            return reader.get_all_data()

        elif protocol_name == "ScallopBorrow":
            print("\t\tgetting ScallopBorrow rates:")
            config = ScallopReaderConfig(
                node_script_path="data/scallop_shared/scallop_reader-sdk.mjs"
            )
            reader = ScallopBorrowReader(config)
            return reader.get_all_data()
        elif protocol_name == "Pebble":
            print("\t\tgetting Pebble rates:")
            reader = PebbleReader()
            return reader.get_all_data()

        else:
            raise ValueError(f"Unknown protocol: {protocol_name}")

    except Exception as e:
        print(f"\t\t⚠️  ERROR ({type(e).__name__}): Failed to fetch {protocol_name} data: {e}")
        print(f"\t\t   Error type: {type(e).__name__}")
        print(f"\t\t   Continuing with other protocols...")
        # Return empty DataFrames to allow pipeline to continue
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def get_rate_for_contract(df: pd.DataFrame, contract: str, value_column: str) -> float:
    """
    Get rate for a specific contract from a DataFrame.

    Args:
        df: DataFrame with Token_coin_type and value columns
        contract: Normalized contract address
        value_column: Column name to extract (e.g., "Supply_apr")

    Returns:
        Rate value or NaN if not found
    """
    if df.empty or 'Token_coin_type' not in df.columns or value_column not in df.columns:
        return float('nan')

    for _, row in df.iterrows():
        if normalize_coin_type(row.get('Token_coin_type', '')) == contract:
            value = row.get(value_column)
            return float(value) if pd.notna(value) else float('nan')

    return float('nan')


def fetch_perp_tokens_at_timestamp(timestamp: int):
    """
    Fetch perp tokens from rates_snapshot at given timestamp where perp_margin_rate IS NOT NULL.

    Args:
        timestamp: Unix timestamp in seconds (the "current time" per DESIGN_NOTES.md #1)

    Returns:
        Dict mapping token_contract -> symbol
        Example: {'0xBTC-USDC-PERP_bluefin': 'BTC'}

    Note: Uses timestamp <= query per DESIGN_NOTES.md #1 (historical context principle)
    """
    try:
        from dashboard.db_utils import get_db_engine
        from utils.time_helpers import to_datetime_str  # DESIGN_NOTES.md #5

        engine = get_db_engine()

        # Convert timestamp to datetime string for SQL query (DESIGN_NOTES.md #5)
        timestamp_str = to_datetime_str(timestamp)

        # Query: Get most recent perp tokens UP TO the selected timestamp
        # Per DESIGN_NOTES.md #1: "selected timestamp IS the current time"
        query = """
            SELECT DISTINCT
                token_contract,
                token as symbol
            FROM rates_snapshot
            WHERE protocol = 'Bluefin'
              AND perp_margin_rate IS NOT NULL
              AND timestamp <= %s
            ORDER BY token
        """

        df = pd.read_sql_query(query, engine, params=(timestamp_str,))

        # Return as dict: {token_contract: symbol}
        return dict(zip(df['token_contract'], df['symbol']))

    except Exception as e:
        print(f"\t\t⚠️  ERROR ({type(e).__name__}): Failed to fetch perp tokens: {e}")
        print(f"\t\t   Continuing without perp data...")
        return {}


def fetch_perp_rate_at_timestamp(token_contract: str, timestamp: int):
    """
    Fetch perp funding rate for a given token contract from rates_snapshot AT the given timestamp.

    Args:
        token_contract: Normalized token contract (e.g., '0xBTC-USDC-PERP_bluefin')
        timestamp: Unix timestamp in seconds (REQUIRED, NO DEFAULT per DESIGN_NOTES.md #2)

    Returns:
        Perp funding rate (annualized decimal, e.g., 0.0876 = 8.76% APR) or None

    CRITICAL: NO datetime.now() fallback. Timestamp must be explicit.
              Per DESIGN_NOTES.md #1: "selected timestamp IS the current time"
    """
    try:
        from dashboard.db_utils import get_db_engine
        from utils.time_helpers import to_datetime_str  # DESIGN_NOTES.md #5

        engine = get_db_engine()

        # Convert timestamp to datetime string for SQL (DESIGN_NOTES.md #5)
        timestamp_str = to_datetime_str(timestamp)

        # Get rate at exact timestamp (or closest before it)
        # Per DESIGN_NOTES.md #1: Use "<= timestamp" for historical context
        query = """
            SELECT perp_margin_rate
            FROM rates_snapshot
            WHERE token_contract = %s
              AND protocol = 'Bluefin'
              AND perp_margin_rate IS NOT NULL
              AND timestamp <= %s
            ORDER BY timestamp DESC
            LIMIT 1
        """
        params = (token_contract, timestamp_str)

        df = pd.read_sql_query(query, engine, params=params)

        if df.empty:
            return None

        return df['perp_margin_rate'].iloc[0]

    except Exception as e:
        # Fail silently for individual token lookups to not break entire merge
        return None


def merge_protocol_data(
    stablecoin_contracts: Set[str] = None,
    timestamp: int = None  # NEW: Unix seconds (int), REQUIRED for perp rates
) -> Tuple[
    pd.DataFrame,  # lend_rates
    pd.DataFrame,  # borrow_rates
    pd.DataFrame,  # collateral_ratios
    pd.DataFrame,  # prices
    pd.DataFrame,  # lend_rewards
    pd.DataFrame,  # borrow_rewards
    pd.DataFrame,  # available_borrow
    pd.DataFrame,  # borrow_fees
    pd.DataFrame,  # borrow_weights
    pd.DataFrame   # liquidation_thresholds
]:
    """
    Merge data from all protocols into unified DataFrames.

    Args:
        stablecoin_contracts: Set of stablecoin contract addresses
        timestamp: Unix timestamp in seconds (REQUIRED when fetching perp rates)
                   Represents "current time" for data fetching (DESIGN_NOTES.md #1)
                   NO DEFAULT - must be passed explicitly

    Returns:
        Tuple of (lend_rates_df, borrow_rates_df, collateral_ratios_df,
                prices_df, lend_rewards_df, borrow_rewards_df,
                available_borrow_df, borrow_fees_df, borrow_weights_df,
                liquidation_thresholds_df)

        Each DataFrame has structure:
            Token | Contract | Navi | AlphaFi | Suilend | ... | perp_margin_rate
    """
    # Fail loudly if timestamp not provided (DESIGN_NOTES.md #2: No datetime.now() defaults)
    if timestamp is None:
        raise ValueError(
            "timestamp parameter is REQUIRED (DESIGN_NOTES.md #2: No datetime.now() defaults). "
            "Pass the strategy timestamp explicitly from the call chain."
        )

    # Default to config stablecoins if not provided
    if stablecoin_contracts is None:
        stablecoin_contracts = STABLECOIN_CONTRACTS
    
    # Normalize all stablecoin contracts for matching
    stablecoin_contracts = {normalize_coin_type(c) for c in stablecoin_contracts}
    
    protocols = ["Navi", "AlphaFi", "Suilend", "ScallopLend", "ScallopBorrow", "Pebble"]
    protocol_data = {}
    
    # Fetch all protocol data
    for protocol in protocols:
        lend, borrow, collateral = fetch_protocol_data(protocol)
        protocol_data[protocol] = {
            'lend': lend,
            'borrow': borrow,
            'collateral': collateral
        }
    
    # Build universe of all tokens by contract
    token_universe = {}  # normalized_contract -> {symbol, protocols}
    
    for protocol in protocols:
        for df_type in ['lend', 'borrow', 'collateral']:
            df = protocol_data[protocol][df_type]
            
            if df.empty or 'Token_coin_type' not in df.columns:
                continue
            
            for _, row in df.iterrows():
                contract = normalize_coin_type(row.get('Token_coin_type', ''))
                symbol = row.get('Token', '')
                
                if contract and symbol:
                    if contract not in token_universe:
                        token_universe[contract] = {
                            'symbol': symbol,
                            'protocols': set()
                        }
                    token_universe[contract]['protocols'].add(protocol)

    # NEW: Add perp tokens to token universe
    print("\t\tFetching perp tokens...")
    perp_tokens = fetch_perp_tokens_at_timestamp(timestamp)
    if perp_tokens:
        print(f"\t\tFound {len(perp_tokens)} perp tokens")
        for token_contract, symbol in perp_tokens.items():
            contract = normalize_coin_type(token_contract)
            if contract not in token_universe:
                token_universe[contract] = {
                    'symbol': symbol,
                    'protocols': set(),  # Perp tokens don't appear in lending protocols
                    'is_perp_token': True  # Mark as perp token for filter exemption
                }
            # Don't add to protocols set - perp rate will be its own column
    else:
        print("\t\tNo perp tokens found")

    # Build merged DataFrames
    lend_rows = []
    borrow_rows = []
    collateral_rows = []
    price_rows = []          # NEW
    lend_reward_rows = []    # NEW
    borrow_reward_rows = []  # NEW
    available_borrow_rows = []  # NEW
    borrow_fee_rows = []  # NEW
    borrow_weight_rows = []  # NEW
    liquidation_thresholds_rows = []  # NEW: LLTV tracking

    for contract, info in token_universe.items():
        symbol = info['symbol']
        
        # Build lend rate row
        lend_row = {'Token': symbol, 'Contract': contract}
        for protocol in protocols:
            df = protocol_data[protocol]['lend']
            rate = get_rate_for_contract(df, contract, 'Supply_apr')
            lend_row[protocol] = rate

        # NEW: Add perp_margin_rate column (separate from protocol columns)
        perp_rate = fetch_perp_rate_at_timestamp(contract, timestamp)
        lend_row['perp_margin_rate'] = perp_rate

        lend_rows.append(lend_row)
        
        # Build borrow rate row
        borrow_row = {'Token': symbol, 'Contract': contract}
        for protocol in protocols:
            df = protocol_data[protocol]['borrow']
            rate = get_rate_for_contract(df, contract, 'Borrow_apr')
            borrow_row[protocol] = rate
        borrow_rows.append(borrow_row)
        
        # Build collateral ratio row
        collateral_row = {'Token': symbol, 'Contract': contract}
        for protocol in protocols:
            df = protocol_data[protocol]['collateral']
            ratio = get_rate_for_contract(df, contract, 'Collateralization_factor')
            collateral_row[protocol] = ratio
        collateral_rows.append(collateral_row)
        # NEW: Build price row
        price_row = {'Token': symbol, 'Contract': contract}
        for protocol in protocols:
            df = protocol_data[protocol]['lend']  # Get from lend df (has Price column)
            price = get_rate_for_contract(df, contract, 'Price')
            price_row[protocol] = price
        price_rows.append(price_row)

        # NEW: Build lend reward row
        lend_reward_row = {'Token': symbol, 'Contract': contract}
        for protocol in protocols:
            df = protocol_data[protocol]['lend']
            reward = get_rate_for_contract(df, contract, 'Supply_reward_apr')
            lend_reward_row[protocol] = reward
        lend_reward_rows.append(lend_reward_row)

        # NEW: Build borrow reward row
        borrow_reward_row = {'Token': symbol, 'Contract': contract}
        for protocol in protocols:
            df = protocol_data[protocol]['borrow']
            reward = get_rate_for_contract(df, contract, 'Borrow_reward_apr')
            borrow_reward_row[protocol] = reward
        borrow_reward_rows.append(borrow_reward_row)

        # NEW: Build available borrow row
        available_borrow_row = {'Token': symbol, 'Contract': contract}
        for protocol in protocols:
            df = protocol_data[protocol]['lend']  # liquidity data in lend df
            available_borrow = get_rate_for_contract(df, contract, 'Available_borrow_usd')
            available_borrow_row[protocol] = available_borrow
        available_borrow_rows.append(available_borrow_row)

        # NEW: Build borrow fee row
        borrow_fee_row = {'Token': symbol, 'Contract': contract}
        for protocol in protocols:
            df = protocol_data[protocol]['lend']  # Fees are in lend df
            # All protocols now return 'Borrow_fee' in decimal format
            fee = get_rate_for_contract(df, contract, 'Borrow_fee')
            borrow_fee_row[protocol] = fee
        borrow_fee_rows.append(borrow_fee_row)

        # NEW: Build borrow weight row
        borrow_weight_row = {'Token': symbol, 'Contract': contract}
        for protocol in protocols:
            df = protocol_data[protocol]['borrow']
            weight = get_rate_for_contract(df, contract, 'Borrow_weight')
            borrow_weight_row[protocol] = weight if not pd.isna(weight) else 1.0  # Default 1.0
        borrow_weight_rows.append(borrow_weight_row)

        # NEW: Build liquidation threshold row
        liquidation_threshold_row = {'Token': symbol, 'Contract': contract}
        for protocol in protocols:
            df = protocol_data[protocol]['borrow']
            ltv = get_rate_for_contract(df, contract, 'Liquidation_ltv')
            liquidation_threshold_row[protocol] = ltv if not pd.isna(ltv) else 0.0  # Default 0.0
        liquidation_thresholds_rows.append(liquidation_threshold_row)

    lend_df = pd.DataFrame(lend_rows)
    borrow_df = pd.DataFrame(borrow_rows)
    collateral_df = pd.DataFrame(collateral_rows)
    prices_df = pd.DataFrame(price_rows)              # NEW
    lend_rewards_df = pd.DataFrame(lend_reward_rows)  # NEW
    borrow_rewards_df = pd.DataFrame(borrow_reward_rows)  # NEW
    available_borrow_df = pd.DataFrame(available_borrow_rows)  # NEW
    borrow_fees_df = pd.DataFrame(borrow_fee_rows)  # NEW
    borrow_weights_df = pd.DataFrame(borrow_weight_rows)  # NEW
    liquidation_thresholds_df = pd.DataFrame(liquidation_thresholds_rows)  # NEW: LLTV

    # Filter: Remove tokens that are only in one protocol (unless they're stablecoins)
    # Matching by CONTRACT ADDRESS (not symbol) for accuracy
    print(f"\n[FILTER] Token universe before filter: {len(lend_df)} tokens")

    tokens_to_keep = []

    for idx, row in lend_df.iterrows():
        contract = normalize_coin_type(row['Contract'])

        # Count unique protocols, treating ScallopLend + ScallopBorrow as one (Scallop)
        has_navi = pd.notna(row.get('Navi'))
        has_alphafi = pd.notna(row.get('AlphaFi'))
        has_suilend = pd.notna(row.get('Suilend'))
        # Count Scallop as present if EITHER ScallopLend OR ScallopBorrow has data
        has_scallop = pd.notna(row.get('ScallopLend')) or pd.notna(row.get('ScallopBorrow'))
        has_pebble = pd.notna(row.get('Pebble'))  

        lending_protocol_count = sum([has_pebble, has_navi, has_alphafi, has_suilend, has_scallop])

        # NEW: Check if this is a perp token
        is_perp = contract in token_universe and token_universe[contract].get('is_perp_token', False)
        has_perp_rate = pd.notna(row.get('perp_margin_rate'))

        # Keep if:
        # 1. Stablecoin in 1+ protocols
        # 2. OR has lending rates in 2+ unique protocols
        # 3. OR is perp token with perp_margin_rate (NEW)
        if contract in stablecoin_contracts or lending_protocol_count >= 2 or (is_perp and has_perp_rate):
            tokens_to_keep.append(idx)
            if is_perp and has_perp_rate:
                print(f"  [FILTER] Keeping perp token {row['Token']} ({contract}) with funding rate {row['perp_margin_rate']:.4%}")

    print(f"[FILTER] Tokens kept: {len(tokens_to_keep)} tokens")
    print(f"[FILTER] Tokens removed: {len(lend_df) - len(tokens_to_keep)} tokens ({((len(lend_df) - len(tokens_to_keep)) / len(lend_df) * 100):.1f}%)")

    # Show breakdown by protocol count (for debugging)
    protocol_counts = {}
    for idx, row in lend_df.iterrows():
        contract = normalize_coin_type(row['Contract'])
        # Count unique protocols (Scallop = ScallopLend OR ScallopBorrow)
        has_navi = pd.notna(row.get('Navi'))
        has_alphafi = pd.notna(row.get('AlphaFi'))
        has_suilend = pd.notna(row.get('Suilend'))
        has_scallop = pd.notna(row.get('ScallopLend')) or pd.notna(row.get('ScallopBorrow'))
        count = sum([has_navi, has_alphafi, has_suilend, has_scallop])
        is_stable = contract in stablecoin_contracts
        key = f"{count} protocols" + (" (stablecoin)" if is_stable else "")
        protocol_counts[key] = protocol_counts.get(key, 0) + 1

    print(f"[FILTER] Breakdown by protocol count (treating Scallop as 1 protocol):")
    for key in sorted(protocol_counts.keys(), key=lambda x: int(x.split()[0])):
        print(f"  {key}: {protocol_counts[key]} tokens")
    
    # Filter all dataframes
    lend_df = lend_df.loc[tokens_to_keep].reset_index(drop=True)
    borrow_df = borrow_df.loc[tokens_to_keep].reset_index(drop=True)
    collateral_df = collateral_df.loc[tokens_to_keep].reset_index(drop=True)
    prices_df = prices_df.loc[tokens_to_keep].reset_index(drop=True)              # NEW
    lend_rewards_df = lend_rewards_df.loc[tokens_to_keep].reset_index(drop=True)  # NEW
    borrow_rewards_df = borrow_rewards_df.loc[tokens_to_keep].reset_index(drop=True)  # NEW
    available_borrow_df = available_borrow_df.loc[tokens_to_keep].reset_index(drop=True)  # NEW
    borrow_fees_df = borrow_fees_df.loc[tokens_to_keep].reset_index(drop=True)  # NEW
    borrow_weights_df = borrow_weights_df.loc[tokens_to_keep].reset_index(drop=True)  # NEW
    liquidation_thresholds_df = liquidation_thresholds_df.loc[tokens_to_keep].reset_index(drop=True)  # NEW: LLTV

    return lend_df, borrow_df, collateral_df, prices_df, lend_rewards_df, borrow_rewards_df, available_borrow_df, borrow_fees_df, borrow_weights_df, liquidation_thresholds_df
