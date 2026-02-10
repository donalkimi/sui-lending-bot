#!/usr/bin/env python3
"""Check portfolio_id values in positions table."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.dashboard_utils import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# Check portfolio_id distribution
cursor.execute("""
    SELECT
        portfolio_id,
        COUNT(*) as count
    FROM positions
    GROUP BY portfolio_id
    ORDER BY count DESC
""")

results = cursor.fetchall()

print("Portfolio ID Distribution:")
print("=" * 60)
for portfolio_id, count in results:
    if portfolio_id is None:
        print(f"  NULL: {count} positions")
    else:
        print(f"  {portfolio_id}: {count} positions")

cursor.close()
conn.close()
