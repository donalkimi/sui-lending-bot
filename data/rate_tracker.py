"""
Rate Tracker - Save protocol data to database

Supports both SQLite (local) and PostgreSQL (Supabase) for easy cloud migration.
"""

import sqlite3
from datetime import datetime, timezone
import pandas as pd
from pathlib import Path
from typing import Optional, List
import psycopg2


class RateTracker:
    """Track lending rates and prices over time"""
    
    def __init__(self, use_cloud=True, db_path='data/lending_rates.db', connection_url=None):
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
            print(f"[DB] RateTracker: Using PostgreSQL (Supabase)")
        else:
            self.db_type = 'sqlite'
            # Ensure data directory exists
            Path(db_path).parent.mkdir(exist_ok=True)
            print(f"[DB] RateTracker: Using SQLite ({db_path})")

        # Create cache tables
        self._create_cache_tables()
    
    def _get_connection(self):
        """Get database connection based on configuration"""
        if self.use_cloud:
            if not self.connection_url:
                raise ValueError("PostgreSQL connection_url required when use_cloud=True")
            if psycopg2 is None:
                raise ImportError("psycopg2 is required for PostgreSQL support. Install with: pip install psycopg2-binary")
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
        borrow_rewards: Optional[pd.DataFrame] = None,
        available_borrow: Optional[pd.DataFrame] = None,
        borrow_fees: Optional[pd.DataFrame] = None,
        borrow_weights: Optional[pd.DataFrame] = None,
        liquidation_thresholds: Optional[pd.DataFrame] = None
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
                collateral_ratios, prices, lend_rewards, borrow_rewards,
                available_borrow, borrow_fees, borrow_weights, liquidation_thresholds
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

            print(f"[DB] Saved snapshot: {rows_saved} rates, {reward_rows} rewards @ {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")

            # Validate snapshot quality
            self._validate_snapshot_quality(conn, timestamp, rows_saved)

        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Error saving snapshot: {e}")
            raise
        finally:
            conn.close()

    def save_position_statistics(self, stats: dict):
        """
        Save position statistics to database.

        Args:
            stats: Dictionary containing position statistics
                {
                    'position_id': str,
                    'timestamp': int,  # Unix seconds
                    'total_pnl': float,
                    'total_earnings': float,
                    'base_earnings': float,
                    'reward_earnings': float,
                    'total_fees': float,
                    'current_value': float,
                    'realized_apr': float,
                    'current_apr': float,
                    'live_pnl': float,
                    'realized_pnl': float,
                    'calculation_timestamp': int  # Unix seconds when calculated
                }
        """
        conn = self._get_connection()

        try:
            # Convert Unix timestamps to datetime strings for database
            from datetime import datetime
            timestamp_str = datetime.fromtimestamp(stats['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            calc_timestamp_str = datetime.fromtimestamp(stats['calculation_timestamp']).strftime('%Y-%m-%d %H:%M:%S')

            # Convert all numeric values to native Python types (handle numpy types)
            total_pnl = self._convert_to_native_types(stats['total_pnl'])
            total_earnings = self._convert_to_native_types(stats['total_earnings'])
            base_earnings = self._convert_to_native_types(stats['base_earnings'])
            reward_earnings = self._convert_to_native_types(stats['reward_earnings'])
            total_fees = self._convert_to_native_types(stats['total_fees'])
            current_value = self._convert_to_native_types(stats['current_value'])
            realized_apr = self._convert_to_native_types(stats['realized_apr'])
            current_apr = self._convert_to_native_types(stats['current_apr'])
            live_pnl = self._convert_to_native_types(stats['live_pnl'])
            realized_pnl = self._convert_to_native_types(stats['realized_pnl'])

            if self.use_cloud:
                # PostgreSQL INSERT ... ON CONFLICT DO UPDATE
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO position_statistics (
                        position_id, timestamp, total_pnl, total_earnings, base_earnings,
                        reward_earnings, total_fees, current_value, realized_apr, current_apr,
                        live_pnl, realized_pnl, calculation_timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (position_id, timestamp) DO UPDATE SET
                        total_pnl = EXCLUDED.total_pnl,
                        total_earnings = EXCLUDED.total_earnings,
                        base_earnings = EXCLUDED.base_earnings,
                        reward_earnings = EXCLUDED.reward_earnings,
                        total_fees = EXCLUDED.total_fees,
                        current_value = EXCLUDED.current_value,
                        realized_apr = EXCLUDED.realized_apr,
                        current_apr = EXCLUDED.current_apr,
                        live_pnl = EXCLUDED.live_pnl,
                        realized_pnl = EXCLUDED.realized_pnl,
                        calculation_timestamp = EXCLUDED.calculation_timestamp
                """, (
                    stats['position_id'],
                    timestamp_str,
                    total_pnl,
                    total_earnings,
                    base_earnings,
                    reward_earnings,
                    total_fees,
                    current_value,
                    realized_apr,
                    current_apr,
                    live_pnl,
                    realized_pnl,
                    calc_timestamp_str
                ))
            else:
                # SQLite INSERT OR REPLACE
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO position_statistics (
                        position_id, timestamp, total_pnl, total_earnings, base_earnings,
                        reward_earnings, total_fees, current_value, realized_apr, current_apr,
                        live_pnl, realized_pnl, calculation_timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stats['position_id'],
                    timestamp_str,
                    total_pnl,
                    total_earnings,
                    base_earnings,
                    reward_earnings,
                    total_fees,
                    current_value,
                    realized_apr,
                    current_apr,
                    live_pnl,
                    realized_pnl,
                    calc_timestamp_str
                ))

            conn.commit()

        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Error saving position statistics for {stats['position_id']}: {e}")
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
        prices: Optional[pd.DataFrame],
        lend_rewards: Optional[pd.DataFrame] = None,
        borrow_rewards: Optional[pd.DataFrame] = None,
        available_borrow: Optional[pd.DataFrame] = None,
        borrow_fees: Optional[pd.DataFrame] = None,
        borrow_weights: Optional[pd.DataFrame] = None,
        liquidation_thresholds: Optional[pd.DataFrame] = None
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
            available_borrow_row = available_borrow[available_borrow['Contract'] == token_contract].iloc[0] if available_borrow is not None and not available_borrow.empty else None
            borrow_fee_row = borrow_fees[borrow_fees['Contract'] == token_contract].iloc[0] if borrow_fees is not None and not borrow_fees.empty else None
            borrow_weight_row = borrow_weights[borrow_weights['Contract'] == token_contract].iloc[0] if borrow_weights is not None and not borrow_weights.empty else None
            liquidation_threshold_row = liquidation_thresholds[liquidation_thresholds['Contract'] == token_contract].iloc[0] if liquidation_thresholds is not None and not liquidation_thresholds.empty else None
            lend_reward_row = lend_rewards[lend_rewards['Contract'] == token_contract].iloc[0] if lend_rewards is not None and not lend_rewards.empty else None
            borrow_reward_row = borrow_rewards[borrow_rewards['Contract'] == token_contract].iloc[0] if borrow_rewards is not None and not borrow_rewards.empty else None

            # For each protocol
            for protocol in protocols:
                # Get total APRs (already calculated correctly by protocol readers)
                # Note: lend_rates contains Supply_apr (total), borrow_rates contains Borrow_apr (total)
                lend_total_apr = lend_row.get(protocol) if pd.notna(lend_row.get(protocol)) else None
                borrow_total_apr = borrow_row.get(protocol) if borrow_row is not None and pd.notna(borrow_row.get(protocol)) else None

                collateral_ratio = collateral_row.get(protocol) if collateral_row is not None and pd.notna(collateral_row.get(protocol)) else None
                price_usd = price_row.get(protocol) if price_row is not None and pd.notna(price_row.get(protocol)) else None
                available_borrow_usd = available_borrow_row.get(protocol) if available_borrow_row is not None and pd.notna(available_borrow_row.get(protocol)) else None
                borrow_fee = borrow_fee_row.get(protocol) if borrow_fee_row is not None and pd.notna(borrow_fee_row.get(protocol)) else None
                borrow_weight = borrow_weight_row.get(protocol) if borrow_weight_row is not None and pd.notna(borrow_weight_row.get(protocol)) else 1.0
                liquidation_threshold = liquidation_threshold_row.get(protocol) if liquidation_threshold_row is not None and pd.notna(liquidation_threshold_row.get(protocol)) else 0.0

                # Get reward APRs (for separate storage)
                lend_reward_apr = lend_reward_row.get(protocol) if lend_reward_row is not None and pd.notna(lend_reward_row.get(protocol)) else 0.0
                borrow_reward_apr = borrow_reward_row.get(protocol) if borrow_reward_row is not None and pd.notna(borrow_reward_row.get(protocol)) else 0.0

                # Calculate base APRs from total and reward (reverse calculation)
                # For lending: base = total - reward (since total = base + reward)
                # For borrowing: base = total + reward (since total = base - reward)
                lend_base_apr = (lend_total_apr - lend_reward_apr) if lend_total_apr is not None else None
                borrow_base_apr = (borrow_total_apr + borrow_reward_apr) if borrow_total_apr is not None else None

                # Skip if no data for this protocol/token combination
                if lend_total_apr is None and borrow_total_apr is None:
                    continue
                
                rows.append({
                    'timestamp': timestamp,
                    'protocol': protocol,
                    'token': token,
                    'token_contract': token_contract,
                    'lend_base_apr': lend_base_apr,
                    'lend_reward_apr': lend_reward_apr,
                    'lend_total_apr': lend_total_apr,
                    'borrow_base_apr': borrow_base_apr,
                    'borrow_reward_apr': borrow_reward_apr,
                    'borrow_total_apr': borrow_total_apr,
                    'collateral_ratio': collateral_ratio,
                    'liquidation_threshold': liquidation_threshold,
                    'price_usd': price_usd,
                    'utilization': None,  # Will add later
                    'total_supply_usd': None,  # Will add later
                    'total_borrow_usd': None,  # Will add later
                    'available_borrow_usd': available_borrow_usd,
                    'borrow_fee': borrow_fee,
                    'borrow_weight': borrow_weight,
                })
        
        # Insert rows
        if rows:
            if self.use_cloud:
                self._insert_rates_postgres(conn, rows)
            else:
                self._insert_rates_sqlite(conn, rows)
        
        return len(rows) 
    def _should_use_for_pnl_sqlite(self, cursor, timestamp: datetime, protocol: str, token_contract: str) -> bool:
        """
        SQLite version of _should_use_for_pnl using ? placeholders.
        See _should_use_for_pnl() for full documentation.
        """
        from datetime import timedelta

        hour_start = timestamp.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)

        query = """
        SELECT timestamp
        FROM rates_snapshot
        WHERE timestamp >= ? AND timestamp < ?
          AND protocol = ? AND token_contract = ?
          AND use_for_pnl = 1
        LIMIT 1
        """

        cursor.execute(query, (hour_start, hour_end, protocol, token_contract))
        existing = cursor.fetchone()

        if not existing:
            return True

        existing_ts = existing[0]
        existing_distance = abs((existing_ts - hour_start).total_seconds())
        new_distance = abs((timestamp - hour_start).total_seconds())

        if new_distance < existing_distance:
            cursor.execute("""
                UPDATE rates_snapshot
                SET use_for_pnl = 0
                WHERE timestamp = ? AND protocol = ? AND token_contract = ?
            """, (existing_ts, protocol, token_contract))
            return True

        return False

    def _insert_rates_sqlite(self, conn, rows):
        """Insert rates into SQLite with PnL flag optimization"""
        cursor = conn.cursor()

        for row in rows:
            # Determine if this snapshot should be used for PnL calculations
            use_for_pnl = self._should_use_for_pnl_sqlite(
                cursor,
                row['timestamp'],
                row['protocol'],
                row['token_contract']
            )

            cursor.execute('''
                INSERT OR REPLACE INTO rates_snapshot
                (timestamp, protocol, token, token_contract,
                    lend_base_apr, lend_reward_apr, lend_total_apr,
                    borrow_base_apr, borrow_reward_apr, borrow_total_apr,
                    collateral_ratio, liquidation_threshold, price_usd,
                    utilization, total_supply_usd, total_borrow_usd, available_borrow_usd, borrow_fee, borrow_weight,
                    use_for_pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['timestamp'], row['protocol'], row['token'], row['token_contract'],
                row['lend_base_apr'], row['lend_reward_apr'], row['lend_total_apr'],
                row['borrow_base_apr'], row['borrow_reward_apr'], row['borrow_total_apr'],
                row['collateral_ratio'], row['liquidation_threshold'], row['price_usd'],
                row['utilization'], row['total_supply_usd'], row['total_borrow_usd'],
                row['available_borrow_usd'], row['borrow_fee'], row['borrow_weight'],
                1 if use_for_pnl else 0  # SQLite uses 1/0 for boolean
            ))

    def _convert_to_native_types(self, value):
        """Convert numpy/pandas types to Python native types for PostgreSQL"""
        if value is None:
            return None

        # Check if it's a numpy/pandas type
        if hasattr(value, 'item'):
            # numpy scalar - convert using .item()
            return value.item()

        # Already a native Python type
        return value

    def _should_use_for_pnl(self, cursor, timestamp: datetime, protocol: str, token_contract: str) -> bool:
        """
        Determine if this snapshot should be used for PnL calculations.

        Logic: Query existing snapshots in this hour and check if this is closest to top of hour.
        Ensures exactly one snapshot per hour per (protocol, token) by:
        1. Finding existing flagged snapshot in this hour
        2. Comparing distances from top of hour
        3. Unflagging old snapshot if new one is closer

        Args:
            cursor: Database cursor for queries
            timestamp: Snapshot timestamp
            protocol: Protocol name (e.g., 'Navi', 'Suilend')
            token_contract: Token contract address

        Returns:
            True if this snapshot should be flagged for PnL, False otherwise
        """
        from datetime import timedelta

        # Calculate hour boundaries
        hour_start = timestamp.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)

        # Query existing PnL snapshot in this hour for this protocol/token
        query = """
        SELECT timestamp
        FROM rates_snapshot
        WHERE timestamp >= %s AND timestamp < %s
          AND protocol = %s AND token_contract = %s
          AND use_for_pnl = TRUE
        LIMIT 1
        """

        cursor.execute(query, (hour_start, hour_end, protocol, token_contract))
        existing = cursor.fetchone()

        if not existing:
            # No existing PnL snapshot in this hour - flag this one
            return True

        # Calculate distances from top of hour
        existing_ts = existing[0]
        existing_distance = abs((existing_ts - hour_start).total_seconds())
        new_distance = abs((timestamp - hour_start).total_seconds())

        if new_distance < existing_distance:
            # This snapshot is closer to top of hour - unset old flag and use this one
            cursor.execute("""
                UPDATE rates_snapshot
                SET use_for_pnl = FALSE
                WHERE timestamp = %s AND protocol = %s AND token_contract = %s
            """, (existing_ts, protocol, token_contract))
            return True

        # Existing snapshot is closer - don't flag this one
        return False

    def _insert_rates_postgres(self, conn, rows):
        """Insert rates into PostgreSQL with PnL flag optimization"""
        cursor = conn.cursor()

        for row in rows:
            # Determine if this snapshot should be used for PnL calculations
            # Uses precise approach: finds closest snapshot to top of each hour
            use_for_pnl = self._should_use_for_pnl(
                cursor,
                row['timestamp'],
                row['protocol'],
                row['token_contract']
            )

            # Convert all values to Python native types
            values = (
                row['timestamp'],
                row['protocol'],
                row['token'],
                row['token_contract'],
                self._convert_to_native_types(row['lend_base_apr']),
                self._convert_to_native_types(row['lend_reward_apr']),
                self._convert_to_native_types(row['lend_total_apr']),
                self._convert_to_native_types(row['borrow_base_apr']),
                self._convert_to_native_types(row['borrow_reward_apr']),
                self._convert_to_native_types(row['borrow_total_apr']),
                self._convert_to_native_types(row['collateral_ratio']),
                self._convert_to_native_types(row['liquidation_threshold']),
                self._convert_to_native_types(row['price_usd']),
                self._convert_to_native_types(row['utilization']),
                self._convert_to_native_types(row['total_supply_usd']),
                self._convert_to_native_types(row['total_borrow_usd']),
                self._convert_to_native_types(row['available_borrow_usd']),
                self._convert_to_native_types(row['borrow_fee']),
                self._convert_to_native_types(row['borrow_weight']),
                use_for_pnl  # PnL optimization flag (added 2026-02-10)
            )

            cursor.execute('''
                INSERT INTO rates_snapshot
                (timestamp, protocol, token, token_contract,
                    lend_base_apr, lend_reward_apr, lend_total_apr,
                    borrow_base_apr, borrow_reward_apr, borrow_total_apr,
                    collateral_ratio, liquidation_threshold, price_usd,
                    utilization, total_supply_usd, total_borrow_usd, available_borrow_usd, borrow_fee, borrow_weight,
                    use_for_pnl)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (timestamp, protocol, token_contract)
                DO UPDATE SET
                    lend_base_apr = EXCLUDED.lend_base_apr,
                    lend_reward_apr = EXCLUDED.lend_reward_apr,
                    lend_total_apr = EXCLUDED.lend_total_apr,
                    borrow_base_apr = EXCLUDED.borrow_base_apr,
                    borrow_reward_apr = EXCLUDED.borrow_reward_apr,
                    borrow_total_apr = EXCLUDED.borrow_total_apr,
                    collateral_ratio = EXCLUDED.collateral_ratio,
                    liquidation_threshold = EXCLUDED.liquidation_threshold,
                    price_usd = EXCLUDED.price_usd,
                    utilization = EXCLUDED.utilization,
                    total_supply_usd = EXCLUDED.total_supply_usd,
                    total_borrow_usd = EXCLUDED.total_borrow_usd,
                    available_borrow_usd = EXCLUDED.available_borrow_usd,
                    borrow_fee = EXCLUDED.borrow_fee,
                    borrow_weight = EXCLUDED.borrow_weight,
                    use_for_pnl = EXCLUDED.use_for_pnl
            ''', values)

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

            if not self.use_cloud:
                self._upsert_token_registry_sqlite(conn, ts, df)
            else:
                self._upsert_token_registry_postgres(conn, ts, df)

            total = self._count_table("token_registry", conn=conn)

            if not self.use_cloud:
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
        if not self.use_cloud:
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

    # ---------------------------------------------------------------------
    # Data Quality Validation
    # ---------------------------------------------------------------------
    def _validate_snapshot_quality(self, conn, timestamp: datetime, rows_saved: int) -> None:
        """
        Validate snapshot data quality and send alerts if quality is low.

        Args:
            conn: Database connection
            timestamp: Timestamp of the snapshot
            rows_saved: Number of rows saved in this snapshot
        """
        # Thresholds
        MIN_ROW_COUNT = 20  # Normal snapshots have ~47 rows
        MIN_PROTOCOL_COUNT = 2  # Need at least 2 protocols for cross-protocol strategies

        # Count protocols in current snapshot
        protocol_count = self._count_protocols_in_snapshot(conn, timestamp)

        # Check if data quality is low
        if rows_saved < MIN_ROW_COUNT or protocol_count <= MIN_PROTOCOL_COUNT:
            warning_msg = (
                f"[WARNING] Low data quality detected:\n"
                f"  - Rows saved: {rows_saved} (expected ~47)\n"
                f"  - Protocols: {protocol_count} (expected 3)\n"
                f"  - Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
            print(warning_msg)

            # Send Slack alert
            try:
                from alerts.slack_notifier import SlackNotifier
                notifier = SlackNotifier()

                # Build message for Slack Workflow
                variables = {
                    "title": "⚠️ Data Quality Warning",
                    "rows_saved": str(rows_saved),
                    "expected_rows": "47",
                    "protocols": str(protocol_count),
                    "expected_protocols": "3",
                    "timestamp": timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
                }

                # For classic webhooks, build a message
                message = (
                    f"⚠️ Data Quality Warning\n\n"
                    f"Low data quality detected in snapshot:\n"
                    f"• Rows saved: {rows_saved} (expected ~47)\n"
                    f"• Protocols: {protocol_count} (expected 3)\n"
                    f"• Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                    f"This may indicate protocol API failures or chain downtime."
                )

                notifier.send_message(message, variables=variables)

            except Exception as e:
                print(f"Failed to send Slack alert: {e}")

    def _count_protocols_in_snapshot(self, conn, timestamp: datetime) -> int:
        """
        Count distinct protocols in a specific snapshot

        Args:
            conn: Database connection
            timestamp: Timestamp to check

        Returns:
            Number of distinct protocols
        """
        cur = conn.cursor()

        if self.use_cloud:
            cur.execute(
                "SELECT COUNT(DISTINCT protocol) FROM rates_snapshot WHERE timestamp = %s",
                (timestamp,)
            )
        else:
            cur.execute(
                "SELECT COUNT(DISTINCT protocol) FROM rates_snapshot WHERE timestamp = ?",
                (timestamp,)
            )

        result = cur.fetchone()
        return int(result[0]) if result else 0

    # ---------------------------------------------------------------------
    # Cache Management
    # ---------------------------------------------------------------------
    def _create_cache_tables(self):
        """Create cache tables for analysis and chart data"""
        conn = self._get_connection()
        try:
            if not self.use_cloud:
                # Create analysis_cache table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS analysis_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp_seconds INTEGER NOT NULL,
                        liquidation_distance REAL NOT NULL,
                        results_json TEXT NOT NULL,
                        strategy_count INTEGER,
                        created_at INTEGER NOT NULL,
                        UNIQUE(timestamp_seconds, liquidation_distance)
                    )
                """)

                # Create chart_cache table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chart_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        strategy_hash TEXT NOT NULL,
                        timestamp_seconds INTEGER NOT NULL,
                        chart_html TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        UNIQUE(strategy_hash, timestamp_seconds)
                    )
                """)

                # Create indexes
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_analysis_cache_timestamp
                        ON analysis_cache(timestamp_seconds, liquidation_distance)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chart_cache_strategy
                        ON chart_cache(strategy_hash, timestamp_seconds)
                """)

                conn.commit()
            # PostgreSQL support can be added in future if needed
        finally:
            conn.close()

    def save_analysis_cache(
        self,
        timestamp_seconds: int,
        liquidation_distance: float,
        all_results
    ) -> None:
        """
        Save analysis results to cache.

        Args:
            timestamp_seconds: Unix timestamp (int)
            liquidation_distance: Decimal (0.10 = 10%)
            all_results: DataFrame or list of dicts (from RateAnalyzer.find_best_protocol_pair)
        """
        import json
        import time

        # Convert DataFrame to list of dicts if needed
        if hasattr(all_results, 'to_dict'):
            # It's a DataFrame, convert to list of dicts
            all_results = all_results.to_dict('records')

        results_json = json.dumps(all_results)
        strategy_count = len(all_results)
        created_at = int(time.time())

        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()

                # Adjust placeholder based on database type
                ph = '%s' if self.use_cloud else '?'

                # Use PostgreSQL-compatible UPSERT syntax
                cursor.execute(f"""
                    INSERT INTO analysis_cache
                    (timestamp_seconds, liquidation_distance, results_json, strategy_count, created_at)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
                    ON CONFLICT (timestamp_seconds, liquidation_distance)
                    DO UPDATE SET
                        results_json = EXCLUDED.results_json,
                        strategy_count = EXCLUDED.strategy_count,
                        created_at = EXCLUDED.created_at
                """, (
                    timestamp_seconds,
                    liquidation_distance,
                    results_json,
                    strategy_count,
                    created_at
                ))

                conn.commit()
                print(f"[CACHE SAVE] Database ({self.db_type}): {strategy_count} strategies saved")

                # Clean up old cache entries (keep only last 48 hours)
                self._cleanup_old_cache(conn, created_at)
            finally:
                conn.close()
        except Exception as e:
            print(f"[CACHE SAVE] Warning: Failed to save cache: {e}")
            # Don't crash - caching is optional optimization

    def _cleanup_old_cache(self, conn, current_time: int, retention_hours: int = 48) -> None:
        """
        Remove cache entries older than retention_hours.

        Args:
            conn: Database connection
            current_time: Current Unix timestamp
            retention_hours: Number of hours to retain (default: 48)
        """
        cutoff_time = current_time - (retention_hours * 3600)

        # Adjust placeholder based on database type
        ph = '%s' if self.use_cloud else '?'

        cursor = conn.cursor()

        # Delete old analysis_cache entries
        # Both PostgreSQL and SQLite: created_at is INTEGER (Unix timestamp), compare directly
        cursor.execute(
            f"DELETE FROM analysis_cache WHERE created_at < {ph}",
            (cutoff_time,)
        )
        deleted_analysis = cursor.rowcount

        # Delete old chart_cache entries
        # Handle database type difference: PostgreSQL uses TIMESTAMP, SQLite uses INTEGER
        if self.use_cloud:
            # PostgreSQL: created_at is TIMESTAMP, convert Unix timestamp to TIMESTAMP
            cursor.execute(
                f"DELETE FROM chart_cache WHERE created_at < to_timestamp({ph})",
                (cutoff_time,)
            )
        else:
            # SQLite: created_at is INTEGER (Unix timestamp)
            cursor.execute(
                f"DELETE FROM chart_cache WHERE created_at < {ph}",
                (cutoff_time,)
            )
        deleted_charts = cursor.rowcount

        conn.commit()

        if deleted_analysis > 0 or deleted_charts > 0:
            print(f"[CACHE CLEANUP] Removed {deleted_analysis} analysis entries and {deleted_charts} chart entries older than {retention_hours}h")

    def load_analysis_cache(
        self,
        timestamp_seconds: int,
        liquidation_distance: float,
        start_time: float = None
    ) -> Optional[pd.DataFrame]:
        """
        Load analysis results from cache.

        Returns:
            DataFrame with all strategies (sorted by net_apr descending) or None if not cached
        """
        import json
        import time

        fetch_start = time.time()

        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()

                # Adjust placeholder based on database type
                ph = '%s' if self.use_cloud else '?'

                cursor.execute(f"""
                    SELECT results_json, strategy_count FROM analysis_cache
                    WHERE timestamp_seconds = {ph} AND liquidation_distance = {ph}
                """, (timestamp_seconds, liquidation_distance))

                row = cursor.fetchone()
                if not row:
                    if start_time:
                        elapsed = (time.time() - start_time) * 1000
                        print(f"[{elapsed:7.1f}ms] [CACHE MISS] No cached analysis for timestamp={timestamp_seconds}, liq_dist={liquidation_distance*100:.0f}%")
                    return None

                results_json, strategy_count = row
                all_results = json.loads(results_json)

                # Convert list of dicts to DataFrame (matches RateAnalyzer.find_best_protocol_pair return)
                df = pd.DataFrame(all_results)

                fetch_time = (time.time() - fetch_start) * 1000
                if start_time:
                    elapsed = (time.time() - start_time) * 1000
                    print(f"[{elapsed:7.1f}ms] [CACHE HIT] Loaded {strategy_count} strategies from DB cache ({self.db_type}) in {fetch_time:.1f}ms")
                else:
                    print(f"[CACHE HIT] Loaded {strategy_count} strategies from cache ({self.db_type}) ({fetch_time:.1f}ms)")

                return df
            finally:
                conn.close()
        except Exception as e:
            print(f"[CACHE LOAD] Warning: Failed to load cache: {e}")
            # Return None to fall back to calculation
            return None

    def save_chart_cache(
        self,
        strategy_hash: str,
        timestamp_seconds: int,
        chart_html: str
    ) -> None:
        """Save rendered chart to cache."""
        import time

        created_at = int(time.time())

        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()

                # Adjust placeholder based on database type
                ph = '%s' if self.use_cloud else '?'

                # Use PostgreSQL-compatible UPSERT syntax
                cursor.execute(f"""
                    INSERT INTO chart_cache
                    (strategy_hash, timestamp_seconds, chart_html, created_at)
                    VALUES ({ph}, {ph}, {ph}, {ph})
                    ON CONFLICT (strategy_hash, timestamp_seconds)
                    DO UPDATE SET
                        chart_html = EXCLUDED.chart_html,
                        created_at = EXCLUDED.created_at
                """, (strategy_hash, timestamp_seconds, chart_html, created_at))

                conn.commit()

                # Clean up old cache entries (keep only last 48 hours)
                self._cleanup_old_cache(conn, created_at)
            finally:
                conn.close()
        except Exception as e:
            print(f"[CACHE SAVE] Warning: Failed to save chart cache: {e}")
            # Don't crash - caching is optional optimization

    def load_chart_cache(
        self,
        strategy_hash: str,
        timestamp_seconds: int
    ) -> Optional[str]:
        """Load rendered chart from cache. Returns HTML string or None."""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()

                # Adjust placeholder based on database type
                ph = '%s' if self.use_cloud else '?'

                cursor.execute(f"""
                    SELECT chart_html FROM chart_cache
                    WHERE strategy_hash = {ph} AND timestamp_seconds = {ph}
                """, (strategy_hash, timestamp_seconds))

                row = cursor.fetchone()
                return row[0] if row else None
            finally:
                conn.close()
        except Exception as e:
            print(f"[CACHE LOAD] Warning: Failed to load chart cache: {e}")
            # Return None to fall back to recalculation
            return None

    # ========================================================================
    # PERPETUAL FUNDING RATES (added 2026-02-17)
    # ========================================================================

    def save_perp_rates(self, perp_rates_df: pd.DataFrame) -> int:
        """
        Save perpetual funding rates to perp_margin_rates table.

        Uses ON CONFLICT DO UPDATE to overwrite existing rates.
        This allows Bluefin to revise historical rates.

        Args:
            perp_rates_df: DataFrame with columns:
                - timestamp: Funding rate timestamp (datetime)
                - protocol: 'Bluefin'
                - market: Market symbol (e.g., 'BTC-PERP')
                - market_address: Contract address from Bluefin
                - token_contract: Proxy format ("0xBTC-USDC-PERP_bluefin")
                - base_token: Base token symbol (e.g., 'BTC')
                - quote_token: Quote token symbol (e.g., 'USDC')
                - funding_rate_hourly: Raw hourly rate (decimal)
                - funding_rate_annual: Annualized rate (decimal)
                - next_funding_time: Next funding update timestamp (optional)

        Returns:
            Number of rows inserted/updated
        """
        if perp_rates_df.empty:
            print("[PERP] No rates to save")
            return 0

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            rows_saved = 0

            # Adjust placeholder based on database type
            ph = '%s' if self.use_cloud else '?'

            for _, row in perp_rates_df.iterrows():
                try:
                    # Round timestamp to minute
                    ts = row['timestamp']
                    if isinstance(ts, pd.Timestamp):
                        ts = ts.to_pydatetime()
                    timestamp_rounded = ts.replace(second=0, microsecond=0)

                    # Prepare values - fail loudly if required fields missing
                    # market_address is optional (may not be in all API responses)
                    market_address = row['market_address'] if 'market_address' in row and pd.notna(row['market_address']) else ''

                    # funding_rate_hourly is optional (for reference only)
                    funding_rate_hourly = None
                    if 'funding_rate_hourly' in row and pd.notna(row['funding_rate_hourly']):
                        funding_rate_hourly = float(row['funding_rate_hourly'])

                    # next_funding_time is optional
                    next_funding_time = None
                    if 'next_funding_time' in row and pd.notna(row['next_funding_time']):
                        next_funding_time = row['next_funding_time']

                    values = (
                        timestamp_rounded,
                        row['protocol'],
                        row['market'],
                        market_address,
                        row['token_contract'],
                        row['base_token'],
                        row['quote_token'],
                        funding_rate_hourly,
                        float(row['funding_rate_annual']),
                        next_funding_time
                    )

                except KeyError as e:
                    print(f"[PERP] KeyError processing row: {e}")
                    print(f"[PERP] Available columns: {list(row.index)}")
                    continue
                except Exception as e:
                    print(f"[PERP] Error processing row: {e}")
                    continue

                if self.use_cloud:
                    # PostgreSQL: ON CONFLICT DO UPDATE
                    cursor.execute(f"""
                        INSERT INTO perp_margin_rates (
                            timestamp, protocol, market, market_address, token_contract,
                            base_token, quote_token, funding_rate_hourly, funding_rate_annual,
                            next_funding_time
                        ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                        ON CONFLICT (timestamp, protocol, token_contract)
                        DO UPDATE SET
                            market = EXCLUDED.market,
                            market_address = EXCLUDED.market_address,
                            base_token = EXCLUDED.base_token,
                            quote_token = EXCLUDED.quote_token,
                            funding_rate_hourly = EXCLUDED.funding_rate_hourly,
                            funding_rate_annual = EXCLUDED.funding_rate_annual,
                            next_funding_time = EXCLUDED.next_funding_time
                    """, values)
                else:
                    # SQLite: INSERT OR REPLACE
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO perp_margin_rates (
                            timestamp, protocol, market, market_address, token_contract,
                            base_token, quote_token, funding_rate_hourly, funding_rate_annual,
                            next_funding_time
                        ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                    """, values)

                rows_saved += 1

            conn.commit()
            print(f"[PERP] Saved/updated {rows_saved} perp rates")
            return rows_saved

        except Exception as e:
            conn.rollback()
            print(f"[PERP] Error saving perp rates: {e}")
            raise
        finally:
            conn.close()

    def register_perp_tokens(self, perp_rates_df: pd.DataFrame) -> int:
        """
        Register proxy perp tokens in token_registry table.

        Creates entries with token_symbol like "BTC-USDC-PERP"
        and token_contract like "0xBTC-USDC-PERP_bluefin".

        Args:
            perp_rates_df: DataFrame with token_contract and base_token columns

        Returns:
            Number of tokens registered
        """
        if perp_rates_df.empty:
            return 0

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            tokens_registered = 0

            # Get unique token contracts
            unique_tokens = perp_rates_df[['token_contract', 'base_token', 'quote_token']].drop_duplicates()

            # Adjust placeholder based on database type
            ph = '%s' if self.use_cloud else '?'

            for _, row in unique_tokens.iterrows():
                token_contract = row['token_contract']
                symbol = f"{row['base_token']}-{row['quote_token']}-PERP"

                try:
                    if self.use_cloud:
                        # PostgreSQL: ON CONFLICT DO NOTHING
                        cursor.execute(f"""
                            INSERT INTO token_registry (
                                token_contract, symbol, first_seen, last_seen
                            ) VALUES ({ph}, {ph}, NOW(), NOW())
                            ON CONFLICT (token_contract) DO UPDATE SET
                                last_seen = NOW()
                        """, (token_contract, symbol))
                    else:
                        # SQLite: INSERT OR IGNORE
                        cursor.execute(f"""
                            INSERT OR IGNORE INTO token_registry (
                                token_contract, symbol, first_seen, last_seen
                            ) VALUES ({ph}, {ph}, datetime('now'), datetime('now'))
                        """, (token_contract, symbol))

                        # Update last_seen if already exists
                        cursor.execute(f"""
                            UPDATE token_registry
                            SET last_seen = datetime('now')
                            WHERE token_contract = {ph}
                        """, (token_contract,))

                    tokens_registered += 1

                except Exception as e:
                    print(f"[PERP] Warning: Failed to register token {symbol}: {e}")
                    continue

            conn.commit()
            if tokens_registered > 0:
                print(f"[PERP] Registered {tokens_registered} perp tokens in token_registry")
            return tokens_registered

        except Exception as e:
            conn.rollback()
            print(f"[PERP] Error registering perp tokens: {e}")
            return 0
        finally:
            conn.close()

    def _get_most_recent_perp_rate(
        self,
        conn,
        token_contract: str,
        snapshot_timestamp: datetime
    ) -> Optional[float]:
        """
        Get most recent perp rate <= snapshot_timestamp.

        Uses indexed query for efficiency.
        Implements "most recent seen" interpolation strategy.

        Args:
            conn: Database connection
            token_contract: Proxy token contract (e.g., "0xBTC-USDC-PERP_bluefin")
            snapshot_timestamp: Target timestamp (rates_snapshot timestamp)

        Returns:
            funding_rate_annual or None if no historic rate found
        """
        cursor = conn.cursor()

        # Adjust placeholder based on database type
        ph = '%s' if self.use_cloud else '?'

        cursor.execute(f"""
            SELECT funding_rate_annual
            FROM perp_margin_rates
            WHERE token_contract = {ph}
              AND timestamp <= {ph}
            ORDER BY timestamp DESC
            LIMIT 1
        """, (token_contract, snapshot_timestamp))

        row = cursor.fetchone()
        return float(row[0]) if row and row[0] is not None else None

    def interpolate_perp_rates_to_snapshot(
        self,
        timestamp: datetime,
        strategy: str = "most_recent",
        backfill_existing: bool = False
    ) -> int:
        """
        Populate rates_snapshot.perp_margin_rate via interpolation.

        Uses "most recent rate seen before snapshot time" logic.
        Does NOT use future rates.

        Args:
            timestamp: Target snapshot timestamp (if None, use latest)
            strategy: Interpolation strategy ('most_recent' initially)
            backfill_existing: If True, update existing rows; if False, only new NULL rows

        Returns:
            Number of rows updated

        Algorithm:
            1. Get all (token, protocol, timestamp) from rates_snapshot at timestamp
            2. For each unique token_contract in perp_margin_rates:
                a. Query perp_margin_rates for most recent rate <= timestamp
                b. UPDATE rates_snapshot SET perp_margin_rate = ?
                   WHERE token_contract matches (via base_token)
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            rows_updated = 0

            # Adjust placeholder based on database type
            ph = '%s' if self.use_cloud else '?'

            # Get all unique perp token contracts with data at this timestamp
            cursor.execute(f"""
                SELECT DISTINCT token_contract, base_token
                FROM perp_margin_rates
                WHERE timestamp <= {ph}
            """, (timestamp,))

            perp_tokens = cursor.fetchall()

            if not perp_tokens:
                print(f"[PERP INTERP] No perp rates found before {timestamp}")
                return 0

            print(f"[PERP INTERP] Interpolating for {len(perp_tokens)} perp tokens at {timestamp}")

            for token_contract, base_token in perp_tokens:
                # Get most recent perp rate for this token
                perp_rate = self._get_most_recent_perp_rate(conn, token_contract, timestamp)

                if perp_rate is None:
                    continue

                # Update rates_snapshot rows where token matches base_token
                # This assumes lending tokens have same symbol as perp base token
                if backfill_existing:
                    # Update all rows (including non-NULL)
                    cursor.execute(f"""
                        UPDATE rates_snapshot
                        SET perp_margin_rate = {ph}
                        WHERE timestamp = {ph}
                          AND token = {ph}
                    """, (perp_rate, timestamp, base_token))
                else:
                    # Only update NULL rows
                    cursor.execute(f"""
                        UPDATE rates_snapshot
                        SET perp_margin_rate = {ph}
                        WHERE timestamp = {ph}
                          AND token = {ph}
                          AND perp_margin_rate IS NULL
                    """, (perp_rate, timestamp, base_token))

                rows_updated += cursor.rowcount

            conn.commit()
            print(f"[PERP INTERP] Updated {rows_updated} rates_snapshot rows")
            return rows_updated

        except Exception as e:
            conn.rollback()
            print(f"[PERP INTERP] Error interpolating perp rates: {e}")
            return 0
        finally:
            conn.close()

    def backfill_perp_rates_to_snapshot(
        self,
        start_date: Optional[datetime] = None,
        end_date: datetime = None
    ) -> int:
        """
        Backfill perp_margin_rate column for existing rates_snapshot rows.

        Used when new perp markets are added or historical data is seeded.

        Args:
            start_date: Start of date range (if None, backfill all)
            end_date: End of date range (REQUIRED - caller must pass explicitly)

        Returns:
            Number of rows updated

        Raises:
            ValueError: If end_date is not provided
        """
        if end_date is None:
            raise ValueError(
                "end_date is required for backfill_perp_rates_to_snapshot(). "
                "Pass datetime.now() explicitly at the call site to make time-dependent behavior visible."
            )

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Adjust placeholder based on database type
            ph = '%s' if self.use_cloud else '?'

            # Get all unique timestamps in range with NULL perp_margin_rate
            if start_date is not None:
                cursor.execute(f"""
                    SELECT DISTINCT timestamp
                    FROM rates_snapshot
                    WHERE timestamp >= {ph}
                      AND timestamp <= {ph}
                      AND perp_margin_rate IS NULL
                    ORDER BY timestamp
                """, (start_date, end_date))
            else:
                cursor.execute(f"""
                    SELECT DISTINCT timestamp
                    FROM rates_snapshot
                    WHERE timestamp <= {ph}
                      AND perp_margin_rate IS NULL
                    ORDER BY timestamp
                """, (end_date,))

            timestamps = [row[0] for row in cursor.fetchall()]

            if not timestamps:
                print("[PERP BACKFILL] No timestamps to backfill")
                return 0

            print(f"[PERP BACKFILL] Backfilling {len(timestamps)} timestamps...")

            total_updated = 0
            for i, ts in enumerate(timestamps):
                rows_updated = self.interpolate_perp_rates_to_snapshot(
                    timestamp=ts,
                    backfill_existing=False  # Only NULL values
                )
                total_updated += rows_updated

                if (i + 1) % 100 == 0:
                    print(f"  Progress: {i + 1}/{len(timestamps)} timestamps")

            print(f"[PERP BACKFILL] Backfilled {total_updated} total rows")
            return total_updated

        except Exception as e:
            print(f"[PERP BACKFILL] Error: {e}")
            return 0
        finally:
            conn.close()

    def detect_new_perp_markets(self, perp_rates_df: pd.DataFrame) -> List[str]:
        """
        Detect if any new perp markets were added that weren't in previous data.

        Args:
            perp_rates_df: Latest perp rates DataFrame

        Returns:
            List of new market symbols (e.g., ["BTC-PERP", "ETH-PERP"])
        """
        if perp_rates_df.empty:
            return []

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Get all existing token_contracts in perp_margin_rates
            cursor.execute("""
                SELECT DISTINCT token_contract
                FROM perp_margin_rates
            """)

            existing_contracts = {row[0] for row in cursor.fetchall()}

            # Check which contracts in new data are not in existing
            new_contracts = set(perp_rates_df['token_contract'].unique())
            newly_added = new_contracts - existing_contracts

            if newly_added:
                # Convert token_contracts back to market symbols
                new_markets = []
                for contract in newly_added:
                    # Extract base token from contract (e.g., "0xBTC-USDC-PERP_bluefin" → "BTC-PERP")
                    if "-PERP_" in contract:
                        base = contract.split("-")[0].replace("0x", "")
                        new_markets.append(f"{base}-PERP")

                return new_markets

            return []

        except Exception as e:
            print(f"[PERP] Error detecting new markets: {e}")
            return []
        finally:
            conn.close()

    def get_latest_snapshot_timestamp(self) -> Optional[datetime]:
        """
        Get the most recent timestamp from rates_snapshot table.

        Returns:
            Latest timestamp or None if table is empty
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(timestamp)
                FROM rates_snapshot
            """)
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else None
        except Exception as e:
            print(f"[PERP] Error getting latest snapshot timestamp: {e}")
            return None
        finally:
            conn.close()

    # ========================================================================
    # END PERPETUAL FUNDING RATES
    # ========================================================================

    @staticmethod
    def compute_strategy_hash(strategy: dict) -> str:
        """
        Compute unique hash for strategy based on tokens and protocols.
        Uses contract addresses (not symbols) for uniqueness.

        Args:
            strategy: Strategy dict with token contracts, protocols, and liquidation_distance

        Returns:
            16-character hash (SHA256 truncated)
        """
        import hashlib

        # Use contract addresses for hashing
        key = f"{strategy['token1_contract']}_{strategy['token2_contract']}_{strategy['token3_contract']}"
        key += f"_{strategy['protocol_a']}_{strategy['protocol_b']}"
        key += f"_{strategy.get('liquidation_distance', 0.10)}"

        return hashlib.sha256(key.encode()).hexdigest()[:16]



