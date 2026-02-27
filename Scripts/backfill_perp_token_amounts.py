#!/usr/bin/env python3
"""
Backfill entry_token_amount_3b for perp_borrowing positions.

WHY THIS IS NEEDED:
    When perp_borrowing positions were deployed, the old create_position() code computed:
        entry_token_amount_3b = b_b * deployment / entry_price_3b
    For perp_borrowing, b_b = 0.0 (no second borrow leg), so entry_token_amount_3b = 0
    was stored. The correct leg is sized by l_b (the perp long notional), not b_b.

    With entry_token_amount_3b = 0, the perp funding earnings are calculated as:
        0 tokens × price × rate × time = $0
    Only borrow costs count, showing a fake large loss.

WHAT THIS DOES:
    For each 'perp_borrowing' or 'perp_borrowing_recursive' position where
    entry_token_amount_3b = 0 AND entry_price_3b > 0:
        entry_token_amount_3b = l_b * deployment_usd / entry_price_3b

    This matches the fixed logic in position_service.py create_position().

SAFE TO RE-RUN: Only updates rows where entry_token_amount_3b = 0.

RUN:
    python -m Scripts.backfill_perp_token_amounts
"""

from config import settings
from data.rate_tracker import RateTracker


def backfill_perp_token_amounts():
    tracker = RateTracker(
        use_cloud=settings.USE_CLOUD_DB,
        connection_url=settings.SUPABASE_URL
    )
    conn = tracker._get_connection()
    cursor = conn.cursor()
    ph = '%s' if tracker.use_cloud else '?'

    try:
        # Find affected positions
        cursor.execute(f"""
            SELECT position_id, strategy_type, l_b, deployment_usd,
                   entry_price_3b, entry_token_amount_3b
            FROM positions
            WHERE strategy_type IN ('perp_borrowing', 'perp_borrowing_recursive')
              AND (entry_token_amount_3b = 0 OR entry_token_amount_3b IS NULL)
              AND entry_price_3b IS NOT NULL
              AND entry_price_3b > 0
        """)
        rows = cursor.fetchall()

        if not rows:
            print("No perp_borrowing positions need backfilling.")
            return

        print(f"Found {len(rows)} perp_borrowing position(s) to backfill:\n")

        updated = 0
        for position_id, strategy_type, l_b, deployment_usd, entry_price_3b, old_3b in rows:
            correct_amount = float(l_b) * float(deployment_usd) / float(entry_price_3b)
            print(f"  {position_id[:8]}... [{strategy_type}]")
            print(f"    l_b={l_b}, deployment=${deployment_usd:,.2f}, entry_price_3b={entry_price_3b:.6f}")
            print(f"    entry_token_amount_3b: {old_3b} → {correct_amount:,.2f}")

            cursor.execute(f"""
                UPDATE positions
                SET entry_token_amount_3b = {ph}
                WHERE position_id = {ph}
            """, (correct_amount, position_id))
            updated += 1

        conn.commit()
        print(f"\n✅ Updated {updated} position(s).")
        print("Position statistics will recalculate on next pipeline run.")

    finally:
        conn.close()


if __name__ == '__main__':
    backfill_perp_token_amounts()
