#!/usr/bin/env python3
"""
Delete all real portfolios, keeping only standalone positions.

This script:
1. Queries all portfolios from the portfolios table
2. Deletes each portfolio using PortfolioService.delete_portfolio()
3. Database constraint automatically sets positions' portfolio_id to NULL
4. These positions then appear in the virtual "Single Positions" portfolio

Usage:
    python Scripts/delete_all_portfolios.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.dashboard_utils import get_db_connection
from analysis.portfolio_service import PortfolioService


def delete_all_portfolios():
    """Delete all real portfolios from the database."""

    conn = get_db_connection()
    service = PortfolioService(conn)

    try:
        # Get all active portfolios
        portfolios = service.get_active_portfolios()

        if portfolios.empty:
            print("✅ No portfolios to delete - database is clean")
            return

        print(f"Found {len(portfolios)} portfolio(s) to delete:")
        print("=" * 60)

        # Display what will be deleted
        for _, portfolio in portfolios.iterrows():
            portfolio_id = portfolio['portfolio_id']
            portfolio_name = portfolio['portfolio_name']
            allocated = portfolio['actual_allocated_usd']

            print(f"  - {portfolio_name}")
            print(f"    ID: {portfolio_id}")
            print(f"    Allocated: ${allocated:,.2f}")
            print()

        # Delete each portfolio
        deleted_count = 0
        for _, portfolio in portfolios.iterrows():
            portfolio_id = portfolio['portfolio_id']
            portfolio_name = portfolio['portfolio_name']

            print(f"Deleting: {portfolio_name}...")
            service.delete_portfolio(portfolio_id)
            deleted_count += 1
            print(f"  ✓ Deleted")

        print()
        print("=" * 60)
        print(f"✅ Successfully deleted {deleted_count} portfolio(s)")
        print()
        print("All positions are now standalone (portfolio_id=NULL)")
        print("They will appear in the '🎯 Single Positions' virtual portfolio")

    except Exception as e:
        print(f"❌ Error during deletion: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    print("=" * 60)
    print("Delete All Portfolios")
    print("=" * 60)
    print()
    print("⚠️  WARNING: This will delete portfolio metadata")
    print("   (Positions will be preserved as standalone)")
    print()

    delete_all_portfolios()
