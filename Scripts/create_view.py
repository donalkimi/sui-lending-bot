"""Quick script to create the all_token_prices view"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv('SUPABASE_URL'))
cursor = conn.cursor()

# Create view using CREATE OR REPLACE (PostgreSQL standard)
view_sql = """
CREATE OR REPLACE VIEW all_token_prices AS
SELECT
    timestamp,
    token,
    token_contract,
    price_usd,
    protocol,
    'supply_borrow' as source
FROM rates_snapshot

UNION

SELECT
    timestamp,
    reward_token as token,
    reward_token_contract as token_contract,
    reward_token_price_usd as price_usd,
    NULL as protocol,
    'reward' as source
FROM reward_token_prices;
"""

print("Creating view...")
cursor.execute(view_sql)
conn.commit()

# Verify
cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'VIEW'")
views = [row[0] for row in cursor.fetchall()]
print(f'Success! Views: {views}')

conn.close()
