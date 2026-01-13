"""
Rate Tracker - Save protocol data to database

Supports both SQLite (local) and PostgreSQL (Supabase) for easy cloud migration.
"""

import sqlite3
import psycopg2
from datetime import datetime, timezone
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
        _conn,
        _timestamp: datetime,
        _lend_rewards: Optional[pd.DataFrame],
        _borrow_rewards: Optional[pd.DataFrame]
    ) -> int:
        """
        Save reward token prices (no protocol - last write wins)

        TODO: Extract reward token data from lend_rewards/borrow_rewards DataFrames
        For now, returns 0 (will implement in Step 4)
        """
        # Placeholder - will implement reward extraction in Step 4
        return 0
    

    # ---------------------------------------------------------------------
    # Token registry
    # ---------------------------------------------------------------------
    def upsert_token_registry(
        self,
        tokens_df: pd.DataFrame,
        timestamp: Optional[datetime] = None
    ) -> dict:
        """
        Upsert token contracts into token_registry.

        Expects a DataFrame with at least:
          - token_contract (preferred) OR Token_coin_type
        Optional columns (0/1 or bool):
          - symbol
          - seen_on_navi, seen_on_alphafi, seen_on_suilend
          - seen_as_reserve, seen_as_reward_lend, seen_as_reward_borrow

        Notes:
          - pyth_id and coingecko_id are NOT overwritten here.
          - seen_* flags are "sticky" (once 1, stays 1).
        """
        if tokens_df is None or len(tokens_df) == 0:
            return {"seen": 0, "inserted": 0, "updated": 0, "total": self._count_table("token_registry")}

        ts = timestamp or datetime.now(timezone.utc)

        df = tokens_df.copy()

        # Normalize required column name
        if "token_contract" not in df.columns:
            if "Token_coin_type" in df.columns:
                df = df.rename(columns={"Token_coin_type": "token_contract"})
            else:
                raise ValueError("tokens_df must contain 'token_contract' (or 'Token_coin_type')")

        # Keep only needed columns, fill missing with defaults
        def _col(name, default=0):
            if name not in df.columns:
                df[name] = default
            return name

        _col("symbol", 0)
        for c in [
            "seen_on_navi", "seen_on_alphafi", "seen_on_suilend",
            "seen_as_reserve", "seen_as_reward_lend", "seen_as_reward_borrow"
        ]:
            _col(c, 0)

        # Coerce flags to int 0/1 where possible
        for c in [
            "seen_on_navi", "seen_on_alphafi", "seen_on_suilend",
            "seen_as_reserve", "seen_as_reward_lend", "seen_as_reward_borrow"
        ]:
            df[c] = df[c].fillna(0).astype(int)

        # De-dupe by token_contract (take max for flags, first non-null for symbol)
        agg = {
            "symbol": "first",
            "seen_on_navi": "max",
            "seen_on_alphafi": "max",
            "seen_on_suilend": "max",
            "seen_as_reserve": "max",
            "seen_as_reward_lend": "max",
            "seen_as_reward_borrow": "max",
        }
        df = df.groupby("token_contract", as_index=False).agg(agg)

        token_list = df["token_contract"].tolist()

        conn = self._get_connection()
        try:
            existing = self._get_existing_token_contracts(conn, token_list)
            inserted = len([t for t in token_list if t not in existing])
            updated_count = len(token_list) - inserted

            if self.db_type == "sqlite":
                self._upsert_token_registry_sqlite(conn, ts, df)
            else:
                self._upsert_token_registry_postgres(conn, ts, df)

            total = self._count_table("token_registry", conn=conn)

            if self.db_type == "sqlite":
                conn.commit()
            else:
                conn.commit()

            return {"seen": len(token_list), "inserted": inserted, "updated": updated_count, "total": total}
        finally:
            conn.close()

    def _get_existing_token_contracts(self, conn, token_contracts: list) -> set:
        """Return set of token_contracts already present in token_registry."""
        if not token_contracts:
            return set()

        cur = conn.cursor()
        if self.db_type == "sqlite":
            placeholders = ",".join(["?"] * len(token_contracts))
            cur.execute(f"SELECT token_contract FROM token_registry WHERE token_contract IN ({placeholders})", token_contracts)
        else:
            placeholders = ",".join(["%s"] * len(token_contracts))
            cur.execute(f"SELECT token_contract FROM token_registry WHERE token_contract IN ({placeholders})", token_contracts)
        rows = cur.fetchall()
        return {r[0] for r in rows}

    def _upsert_token_registry_sqlite(self, conn, ts: datetime, df: pd.DataFrame) -> None:
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT INTO token_registry (
                token_contract, symbol, pyth_id, coingecko_id,
                seen_on_navi, seen_on_alphafi, seen_on_suilend,
                seen_as_reserve, seen_as_reward_lend, seen_as_reward_borrow,
                first_seen, last_seen
            )
            VALUES (
                ?, ?, NULL, NULL,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?
            )
            ON CONFLICT(token_contract) DO UPDATE SET
                last_seen = excluded.last_seen,
                -- Keep pyth_id / coingecko_id as-is unless they are NULL and excluded is non-NULL (excluded is NULL here)
                symbol = COALESCE(token_registry.symbol, excluded.symbol),
                seen_on_navi = MAX(token_registry.seen_on_navi, excluded.seen_on_navi),
                seen_on_alphafi = MAX(token_registry.seen_on_alphafi, excluded.seen_on_alphafi),
                seen_on_suilend = MAX(token_registry.seen_on_suilend, excluded.seen_on_suilend),
                seen_as_reserve = MAX(token_registry.seen_as_reserve, excluded.seen_as_reserve),
                seen_as_reward_lend = MAX(token_registry.seen_as_reward_lend, excluded.seen_as_reward_lend),
                seen_as_reward_borrow = MAX(token_registry.seen_as_reward_borrow, excluded.seen_as_reward_borrow)
            """,
            [
                (
                    r["token_contract"],
                    r["symbol"],
                    int(r["seen_on_navi"]),
                    int(r["seen_on_alphafi"]),
                    int(r["seen_on_suilend"]),
                    int(r["seen_as_reserve"]),
                    int(r["seen_as_reward_lend"]),
                    int(r["seen_as_reward_borrow"]),
                    ts,
                    ts,
                )
                for _, r in df.iterrows()
            ],
        )

    def _upsert_token_registry_postgres(self, conn, ts: datetime, df: pd.DataFrame) -> None:
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT INTO token_registry (
                token_contract, symbol, pyth_id, coingecko_id,
                seen_on_navi, seen_on_alphafi, seen_on_suilend,
                seen_as_reserve, seen_as_reward_lend, seen_as_reward_borrow,
                first_seen, last_seen
            )
            VALUES (
                %s, %s, NULL, NULL,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            ON CONFLICT(token_contract) DO UPDATE SET
                last_seen = EXCLUDED.last_seen,
                symbol = COALESCE(token_registry.symbol, EXCLUDED.symbol),
                seen_on_navi = GREATEST(token_registry.seen_on_navi, EXCLUDED.seen_on_navi),
                seen_on_alphafi = GREATEST(token_registry.seen_on_alphafi, EXCLUDED.seen_on_alphafi),
                seen_on_suilend = GREATEST(token_registry.seen_on_suilend, EXCLUDED.seen_on_suilend),
                seen_as_reserve = GREATEST(token_registry.seen_as_reserve, EXCLUDED.seen_as_reserve),
                seen_as_reward_lend = GREATEST(token_registry.seen_as_reward_lend, EXCLUDED.seen_as_reward_lend),
                seen_as_reward_borrow = GREATEST(token_registry.seen_as_reward_borrow, EXCLUDED.seen_as_reward_borrow)
            """,
            [
                (
                    r["token_contract"],
                    r["symbol"],
                    int(r["seen_on_navi"]),
                    int(r["seen_on_alphafi"]),
                    int(r["seen_on_suilend"]),
                    int(r["seen_as_reserve"]),
                    int(r["seen_as_reward_lend"]),
                    int(r["seen_as_reward_borrow"]),
                    ts,
                    ts,
                )
                for _, r in df.iterrows()
            ],
        )

    # ---------------------------------------------------------------------
    # Inspection helpers
    # ---------------------------------------------------------------------
    def get_table_counts(self) -> dict:
        """Return row counts for key tables (if they exist)."""
        conn = self._get_connection()
        try:
            counts = {}
            for table in ["rates_snapshot", "token_registry", "reward_token_prices"]:
                counts[table] = self._count_table(table, conn=conn)
            return counts
        finally:
            conn.close()

    def _count_table(self, table: str, conn=None) -> int:
        """Count rows in a table; returns 0 if table doesn't exist."""
        close_conn = False
        if conn is None:
            conn = self._get_connection()
            close_conn = True
        try:
            cur = conn.cursor()
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                result = cur.fetchone()
                return int(result[0]) if result else 0
            except Exception:
                return 0
        finally:
            if close_conn:
                conn.close()


    
