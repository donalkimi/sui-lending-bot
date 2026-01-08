"""
Rate Tracker - Save protocol data to database

Supports both SQLite (local) and PostgreSQL (Supabase) for easy cloud migration.
"""

import sqlite3
import psycopg2
from datetime import datetime
import pandas as pd
from pathlib import Path
from typing import Optional


class RateTracker:
    """Track lending rates and prices over time"""
    
    def __init__(self, use_cloud=False, db_path='data/lending_rates.db', connection_url=None):
        """
        Initialize rate tracker
        
        Args:
            use_cloud: If True, use PostgreSQL (Supabase). If False, use SQLite.
            db_path: Path to SQLite database file (only used if use_cloud=False)
            connection_url: PostgreSQL connection string (only used if use_cloud=True)
        """
        self.use_cloud = use_cloud
        self.db_path = db_path
        self.connection_url = connection_url
        
        if self.use_cloud:
            self.db_type = 'postgresql'
            print(f"📊 RateTracker: Using PostgreSQL (Supabase)")
        else:
            self.db_type = 'sqlite'
            # Ensure data directory exists
            Path(db_path).parent.mkdir(exist_ok=True)
            print(f"📊 RateTracker: Using SQLite ({db_path})")
    
    def _get_connection(self):
        """Get database connection based on configuration"""
        if self.db_type == 'postgresql':
            if not self.connection_url:
                raise ValueError("PostgreSQL connection_url required when use_cloud=True")
            return psycopg2.connect(self.connection_url)
        else:
            return sqlite3.connect(self.db_path)
    
    def save_snapshot(
        self,
        timestamp: datetime,
        lend_rates: pd.DataFrame,
        borrow_rates: pd.DataFrame,
        collateral_ratios: pd.DataFrame,
        prices: Optional[pd.DataFrame] = None,
        lend_rewards: Optional[pd.DataFrame] = None,
        borrow_rewards: Optional[pd.DataFrame] = None
    ):
        """
        Save a complete snapshot of protocol data
        
        Args:
            timestamp: Snapshot timestamp (datetime object, rounded to minute)
            lend_rates: DataFrame with lending rates (Token, Contract, Protocol1, Protocol2, ...)
            borrow_rates: DataFrame with borrow rates
            collateral_ratios: DataFrame with collateral ratios
            prices: DataFrame with prices (optional, will be added later)
            lend_rewards: DataFrame with lend reward APRs (optional, will be added later)
            borrow_rewards: DataFrame with borrow reward APRs (optional, will be added later)
        """
        conn = self._get_connection()
        
        try:
            # Save rates_snapshot
            rows_saved = self._save_rates_snapshot(
                conn, timestamp, lend_rates, borrow_rates, 
                collateral_ratios, prices
            )
            
            # Save reward_token_prices (if data available)
            if lend_rewards is not None or borrow_rewards is not None:
                reward_rows = self._save_reward_prices(
                    conn, timestamp, lend_rewards, borrow_rewards
                )
            else:
                reward_rows = 0
            
            # Commit
            conn.commit()
            
            print(f"✅ Saved snapshot: {rows_saved} rate rows, {reward_rows} reward price rows")
            print(f"   Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error saving snapshot: {e}")
            raise
        finally:
            conn.close()
    
    def _save_rates_snapshot(
        self, 
        conn, 
        timestamp: datetime,
        lend_rates: pd.DataFrame,
        borrow_rates: pd.DataFrame,
        collateral_ratios: pd.DataFrame,
        prices: Optional[pd.DataFrame]
    ) -> int:
        """Save to rates_snapshot table"""
        
        # Get list of protocols (columns except Token and Contract)
        non_protocol_cols = {'Token', 'Contract'}
        protocols = [col for col in lend_rates.columns if col not in non_protocol_cols]
        
        rows = []
        
        # Build rows for each token/protocol combination
        for _, lend_row in lend_rates.iterrows():
            token = lend_row['Token']
            token_contract = lend_row['Contract']
            
            # Get corresponding rows from other dataframes
            borrow_row = borrow_rates[borrow_rates['Contract'] == token_contract].iloc[0] if not borrow_rates.empty else None
            collateral_row = collateral_ratios[collateral_ratios['Contract'] == token_contract].iloc[0] if not collateral_ratios.empty else None
            price_row = prices[prices['Contract'] == token_contract].iloc[0] if prices is not None and not prices.empty else None
            
            # For each protocol
            for protocol in protocols:
                # Get rates
                lend_base_apr = lend_row.get(protocol) if pd.notna(lend_row.get(protocol)) else None
                borrow_base_apr = borrow_row.get(protocol) if borrow_row is not None and pd.notna(borrow_row.get(protocol)) else None
                collateral_ratio = collateral_row.get(protocol) if collateral_row is not None and pd.notna(collateral_row.get(protocol)) else None
                price_usd = price_row.get(protocol) if price_row is not None and pd.notna(price_row.get(protocol)) else None
                
                # Skip if no data for this protocol/token combination
                if lend_base_apr is None and borrow_base_apr is None:
                    continue
                
                rows.append({
                    'timestamp': timestamp,
                    'protocol': protocol,
                    'token': token,
                    'token_contract': token_contract,
                    'lend_base_apr': lend_base_apr,
                    'lend_reward_apr': None,  # TODO: Extract from lend_rewards
                    'lend_total_apr': lend_base_apr,  # For now, same as base
                    'borrow_base_apr': borrow_base_apr,
                    'borrow_reward_apr': None,  # TODO: Extract from borrow_rewards
                    'borrow_total_apr': borrow_base_apr,  # For now, same as base
                    'collateral_ratio': collateral_ratio,
                    'liquidation_threshold': None,  # TODO: Add if available
                    'price_usd': price_usd,
                    'utilization': None,  # Will add later
                    'total_supply_usd': None,  # Will add later
                    'total_borrow_usd': None,  # Will add later
                    'available_borrow_usd': None,  # Will add later
                })
        
        # Insert rows
        if rows:
            if self.db_type == 'postgresql':
                self._insert_rates_postgres(conn, rows)
            else:
                self._insert_rates_sqlite(conn, rows)
        
        return len(rows)
    
    def _insert_rates_sqlite(self, conn, rows):
        """Insert rates into SQLite"""
        cursor = conn.cursor()
        
        for row in rows:
            cursor.execute('''
                INSERT OR REPLACE INTO rates_snapshot 
                (timestamp, protocol, token, token_contract,
                 lend_base_apr, lend_reward_apr, lend_total_apr,
                 borrow_base_apr, borrow_reward_apr, borrow_total_apr,
                 collateral_ratio, liquidation_threshold, price_usd,
                 utilization, total_supply_usd, total_borrow_usd, available_borrow_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['timestamp'], row['protocol'], row['token'], row['token_contract'],
                row['lend_base_apr'], row['lend_reward_apr'], row['lend_total_apr'],
                row['borrow_base_apr'], row['borrow_reward_apr'], row['borrow_total_apr'],
                row['collateral_ratio'], row['liquidation_threshold'], row['price_usd'],
                row['utilization'], row['total_supply_usd'], row['total_borrow_usd'], 
                row['available_borrow_usd']
            ))
    
    def _insert_rates_postgres(self, conn, rows):
        """Insert rates into PostgreSQL"""
        cursor = conn.cursor()
        
        for row in rows:
            cursor.execute('''
                INSERT INTO rates_snapshot 
                (timestamp, protocol, token, token_contract,
                 lend_base_apr, lend_reward_apr, lend_total_apr,
                 borrow_base_apr, borrow_reward_apr, borrow_total_apr,
                 collateral_ratio, liquidation_threshold, price_usd,
                 utilization, total_supply_usd, total_borrow_usd, available_borrow_usd)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (timestamp, protocol, token_contract) DO NOTHING
            ''', (
                row['timestamp'], row['protocol'], row['token'], row['token_contract'],
                row['lend_base_apr'], row['lend_reward_apr'], row['lend_total_apr'],
                row['borrow_base_apr'], row['borrow_reward_apr'], row['borrow_total_apr'],
                row['collateral_ratio'], row['liquidation_threshold'], row['price_usd'],
                row['utilization'], row['total_supply_usd'], row['total_borrow_usd'], 
                row['available_borrow_usd']
            ))
    
    def _save_reward_prices(
        self,
        conn,
        timestamp: datetime,
        lend_rewards: Optional[pd.DataFrame],
        borrow_rewards: Optional[pd.DataFrame]
    ) -> int:
        """
        Save reward token prices (no protocol - last write wins)
        
        TODO: Extract reward token data from lend_rewards/borrow_rewards DataFrames
        For now, returns 0 (will implement in Step 4)
        """
        # Placeholder - will implement reward extraction in Step 4
        return 0