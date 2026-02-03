"""Migrate missing liquidation columns for position_rebalances"""
import pandas as pd
import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = 'data/lending_rates.db'
SUPABASE_URL = os.getenv('SUPABASE_URL')

# Columns to migrate (case-sensitive in SQLite, will be lowercase in PostgreSQL)
MISSING_REBALANCE_COLUMNS = [
    'closing_liq_price_1A',
    'closing_liq_price_2A',
    'closing_liq_price_2B',
    'closing_liq_price_3B',
    'closing_liq_dist_1A',
    'closing_liq_dist_2A',
    'closing_liq_dist_2B',
    'closing_liq_dist_3B'
]

def migrate_rebalance_columns():
    """Migrate missing liquidation columns in position_rebalances"""
    print("="*60)
    print("Migrating position_rebalances missing columns")
    print("="*60)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    pg_conn = psycopg2.connect(SUPABASE_URL)
    pg_cursor = pg_conn.cursor()

    # Read data from SQLite
    columns_sql = ', '.join(['rebalance_id'] + MISSING_REBALANCE_COLUMNS)
    df = pd.read_sql(f'SELECT {columns_sql} FROM position_rebalances', sqlite_conn)

    print(f"Found {len(df)} rebalance records in SQLite")

    if len(df) == 0:
        print("[WARN] No data to migrate")
        sqlite_conn.close()
        pg_conn.close()
        return

    # Convert column names to lowercase for PostgreSQL
    df.columns = [col.lower() for col in df.columns]

    # Convert numpy types to Python native types
    for col in df.columns:
        if col != 'rebalance_id':
            df[col] = df[col].apply(lambda x: x.item() if hasattr(x, 'item') else x)

    # Update PostgreSQL records
    print(f"Updating {len(df)} records in PostgreSQL...")
    updated = 0
    for _, row in df.iterrows():
        update_cols = []
        values = []

        for col in df.columns:
            if col != 'rebalance_id':
                update_cols.append(f"{col} = %s")
                values.append(row[col])

        values.append(row['rebalance_id'])  # WHERE clause

        sql = f"""
            UPDATE position_rebalances
            SET {', '.join(update_cols)}
            WHERE rebalance_id = %s
        """

        pg_cursor.execute(sql, values)
        updated += 1

    pg_conn.commit()
    print(f"[OK] Updated {updated} records in PostgreSQL")

    # Verify
    pg_cursor.execute("SELECT COUNT(*) FROM position_rebalances WHERE closing_liq_dist_2a IS NOT NULL")
    count = pg_cursor.fetchone()[0]
    print(f"[OK] Records with closing_liq_dist_2a: {count}")

    sqlite_conn.close()
    pg_conn.close()
    print("\n[SUCCESS] Migration complete!")

if __name__ == '__main__':
    try:
        migrate_rebalance_columns()
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
