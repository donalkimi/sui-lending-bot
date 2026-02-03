"""
Clear all analysis cache from local SQLite database
"""
import sqlite3
from pathlib import Path

# Path to the SQLite database
db_path = Path("data/lending_rates.db")

if not db_path.exists():
    print(f"❌ Database not found at {db_path}")
    print("   No cache to clear.")
    exit(0)

# Connect and clear cache
with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()
    
    # Get count before deletion
    cursor.execute("SELECT COUNT(*) FROM analysis_cache")
    count_before = cursor.fetchone()[0]
    
    # Delete all cached analysis
    cursor.execute("DELETE FROM analysis_cache")
    conn.commit()
    
    # Also clear chart cache if you want
    cursor.execute("DELETE FROM chart_cache")
    conn.commit()
    
    print(f"✅ Cleared {count_before} cached strategy analyses")
    print(f"✅ Cleared chart cache")
    print(f"   Database: {db_path}")

print("\n🔄 Next dashboard load will recalculate all strategies from scratch.")