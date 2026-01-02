"""
API Data Enrichment Helper

Merges live API data from protocol readers (Navi, Suilend, AlphaFi) with Google Sheets data.
Called between sheets_reader and rate_analyzer in the main workflow.
"""

import pandas as pd
from typing import Tuple, Dict
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def enrich_with_navi_data(
    lend_df: pd.DataFrame,
    borrow_df: pd.DataFrame,
    collateral_df: pd.DataFrame,
    timeout: int = 10
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict]:
    """
    Enrich Google Sheets data with live Navi API data.
    
    Args:
        lend_df: Lending rates dataframe from Google Sheets
        borrow_df: Borrow rates dataframe from Google Sheets
        collateral_df: Collateral ratios dataframe from Google Sheets
        timeout: API call timeout in seconds (default: 10)
    
    Returns:
        Tuple of (updated_lend_df, updated_borrow_df, updated_collateral_df, metadata)
        
    Metadata dict contains:
        - navi_source: 'API' or 'SHEETS'
        - navi_updated_count: number of tokens updated
        - navi_total_count: total tokens with Navi column
        - navi_updated_at: timestamp of update (if successful)
    """
    from data.navi_reader import NaviReader
    from datetime import datetime
    
    metadata = {
        'navi_source': 'SHEETS',
        'navi_updated_count': 0,
        'navi_total_count': 0,
        'navi_updated_at': None
    }
    
    # Check if Navi column exists in any dataframe
    has_navi_lend = 'Navi' in lend_df.columns
    has_navi_borrow = 'Navi' in borrow_df.columns
    has_navi_collateral = 'Navi' in collateral_df.columns
    
    if not (has_navi_lend or has_navi_borrow or has_navi_collateral):
        print("⚠️  No 'Navi' columns found in Google Sheets - skipping Navi API update")
        return lend_df, borrow_df, collateral_df, metadata
    
    print("\n🔄 Enriching data with live Navi API...")
    
    # Try to fetch live Navi data
    try:
        reader = NaviReader()
        reader.session.timeout = timeout
        
        navi_lend, navi_borrow, navi_collateral = reader.get_all_data()

        metadata['navi_source'] = 'API'
        metadata['navi_updated_at'] = datetime.now().isoformat()
        
        # Update each dataframe
        updated_lend = _update_dataframe(
            sheets_df=lend_df,
            api_df=navi_lend,
            value_column='Supply_apr',
            has_navi=has_navi_lend,
            df_name='lend_rates'
        )
        
        updated_borrow = _update_dataframe(
            sheets_df=borrow_df,
            api_df=navi_borrow,
            value_column='Borrow_apr',
            has_navi=has_navi_borrow,
            df_name='borrow_rates'
        )
        
        updated_collateral = _update_dataframe(
            sheets_df=collateral_df,
            api_df=navi_collateral,
            value_column='Collateralization_factor',
            has_navi=has_navi_collateral,
            df_name='collateral_ratios'
        )
        
        # Count total updates
        total_updated = (
            (updated_lend[1] if has_navi_lend else 0) +
            (updated_borrow[1] if has_navi_borrow else 0) +
            (updated_collateral[1] if has_navi_collateral else 0)
        )
        
        total_tokens = (
            (updated_lend[2] if has_navi_lend else 0) +
            (updated_borrow[2] if has_navi_borrow else 0) +
            (updated_collateral[2] if has_navi_collateral else 0)
        )
        
        metadata['navi_updated_count'] = total_updated
        metadata['navi_total_count'] = total_tokens
        
        print(f"   ✓ Navi data source: API")
        print(f"   ✓ Updated {total_updated}/{total_tokens} token entries from Navi API")
        
        return updated_lend[0], updated_borrow[0], updated_collateral[0], metadata
        
    except Exception as e:
        print(f"   ⚠️  Navi API call failed: {e}")
        print(f"   ⚠️  Using Google Sheets data for Navi (may be stale)")
        return lend_df, borrow_df, collateral_df, metadata


def _update_dataframe(
    sheets_df: pd.DataFrame,
    api_df: pd.DataFrame,
    value_column: str,
    has_navi: bool,
    df_name: str
) -> Tuple[pd.DataFrame, int, int]:
    """
    Update a single dataframe with API data.
    
    Args:
        sheets_df: Original dataframe from Google Sheets
        api_df: API dataframe with live data
        value_column: Column name in API df to extract values from
        has_navi: Whether sheets_df has a 'Navi' column
        df_name: Name for logging
    
    Returns:
        Tuple of (updated_df, updated_count, total_count)
    """
    if not has_navi:
        return sheets_df, 0, 0
    
    # Make a copy to avoid modifying original
    updated_df = sheets_df.copy()
    
    # Check if Contract column exists
    if 'Contract' not in updated_df.columns:
        print(f"   ⚠️  No 'Contract' column in {df_name} - cannot match tokens")
        return updated_df, 0, 0
    
    # Create mapping from API data: contract -> value
    api_mapping = {}
    if 'Token_coin_type' in api_df.columns and value_column in api_df.columns:
        for _, row in api_df.iterrows():
            contract = row['Token_coin_type']
            value = row[value_column]
            if pd.notna(contract) and pd.notna(value):
                api_mapping[contract] = value
    else:
        print(f"   ⚠️  API data missing required columns for {df_name}")
        return updated_df, 0, 0
    
    # Update matching rows
    updated_count = 0
    total_count = 0
    
    for idx, row in updated_df.iterrows():
        contract = row.get('Contract')
        if pd.notna(contract) and contract in api_mapping:
            updated_df.at[idx, 'Navi'] = api_mapping[contract]
            updated_count += 1
        
        # Count total rows that have a contract (even if not updated)
        if pd.notna(contract):
            total_count += 1
    
    return updated_df, updated_count, total_count


# Example usage for testing
if __name__ == "__main__":
    # This would normally be called from main.py with real data
    print("This module should be imported and called from main.py")
    print("\nExample usage:")
    print("from data.api_enricher import enrich_with_navi_data")
    print("lend, borrow, collateral, metadata = enrich_with_navi_data(lend_df, borrow_df, collateral_df)")
