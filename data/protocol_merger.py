"""
Protocol Data Merger

Fetches and merges data from Navi, AlphaFi, and Suilend protocols into unified DataFrames.
"""

import pandas as pd
from typing import Tuple, Set
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.navi_reader import NaviReader
from data.alphalend.alphafi_reader import AlphaFiReader, AlphaFiReaderConfig
from data.suilend.suilend_reader import SuilendReader, SuilendReaderConfig

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
    """
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
        
    else:
        raise ValueError(f"Unknown protocol: {protocol_name}")


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


def merge_protocol_data(stablecoin_contracts: Set[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Merge data from all protocols into unified DataFrames.
    
    Filters out tokens that only exist in one protocol, unless they are stablecoins.
    Stablecoins are kept regardless of protocol count since they're assumed fungible.
    Matching is done by contract address (not symbol) for accuracy.
    
    Args:
        stablecoin_contracts: Set of stablecoin contract addresses 
                             (e.g., {'0xdba3...::usdc::USDC', '0x960b...::usdy::USDY'})
                             If None, uses default set from config/stablecoins.py
    
    Returns:
        Tuple of (lend_rates_df, borrow_rates_df, collateral_ratios_df)
        
        Each DataFrame has structure:
            Token | Contract | Navi | AlphaFi | Suilend
    """
    # Default to config stablecoins if not provided
    if stablecoin_contracts is None:
        stablecoin_contracts = STABLECOIN_CONTRACTS
    
    # Normalize all stablecoin contracts for matching
    stablecoin_contracts = {normalize_coin_type(c) for c in stablecoin_contracts}
    
    protocols = ["Navi", "AlphaFi", "Suilend"]
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
    
    # Build merged DataFrames
    lend_rows = []
    borrow_rows = []
    collateral_rows = []
    
    for contract, info in token_universe.items():
        symbol = info['symbol']
        
        # Build lend rate row
        lend_row = {'Token': symbol, 'Contract': contract}
        for protocol in protocols:
            df = protocol_data[protocol]['lend']
            rate = get_rate_for_contract(df, contract, 'Supply_apr')
            lend_row[protocol] = rate
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
    
    lend_df = pd.DataFrame(lend_rows)
    borrow_df = pd.DataFrame(borrow_rows)
    collateral_df = pd.DataFrame(collateral_rows)
    
    # Filter: Remove tokens that are only in one protocol (unless they're stablecoins)
    # Matching by CONTRACT ADDRESS (not symbol) for accuracy
    tokens_to_keep = []
    
    for idx, row in lend_df.iterrows():
        contract = normalize_coin_type(row['Contract'])
        protocol_count = sum([pd.notna(row[protocol]) for protocol in protocols])
        
        # Keep if: stablecoin (by contract) OR in 2+ protocols
        if contract in stablecoin_contracts or protocol_count >= 2:
            tokens_to_keep.append(idx)
    
    # Filter all dataframes
    lend_df = lend_df.loc[tokens_to_keep].reset_index(drop=True)
    borrow_df = borrow_df.loc[tokens_to_keep].reset_index(drop=True)
    collateral_df = collateral_df.loc[tokens_to_keep].reset_index(drop=True)
    
    return lend_df, borrow_df, collateral_df