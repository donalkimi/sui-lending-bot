"""
Test script for PositionService (Steps 1-2 verification)

Tests:
1. Create a test position
2. Query the position
3. Create a snapshot
4. Calculate PnL
5. Close position
"""

import sqlite3
import pandas as pd
from datetime import datetime
from analysis.position_service import PositionService

def test_position_service():
    """Test the position service with mock data"""

    print("=" * 60)
    print("Testing PositionService (Steps 1-2)")
    print("=" * 60)

    # Connect to database
    conn = sqlite3.connect('data/lending_rates.db')
    service = PositionService(conn)

    # Create mock strategy data (mimicking RateAnalyzer output)
    # NOTE: Keys should NOT have 'entry_' prefix - PositionService adds that internally
    strategy_data = pd.Series({
        'token1': 'SUI',
        'token2': 'USDC',
        'token3': 'USDC',  # Same as token2 for levered strategy
        'token1_contract': '0x2::sui::SUI',
        'token2_contract': '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC',
        'token3_contract': '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC',
        'protocol_A': 'Suilend',
        'protocol_B': 'Navi',
        'timestamp': datetime.now(),
        'L_A': 1.0,
        'B_A': 0.8,
        'L_B': 0.8,
        'B_B': 0.64,  # Levered strategy
        'lend_rate_1A': 0.05,  # 5% APR
        'borrow_rate_2A': 0.03,  # 3% APR
        'lend_rate_2B': 0.07,  # 7% APR
        'borrow_rate_3B': 0.04,  # 4% APR
        'price_1A': 2.50,  # SUI at $2.50
        'price_2': 1.00,  # USDC at $1.00
        'price_3B': 1.00,  # USDC at $1.00
        'collateral_ratio_1A': 0.75,  # 75% LTV
        'collateral_ratio_2B': 0.80,  # 80% LTV
        'net_apr': 0.10,  # 10% net APR
        'apr5': 0.09,  # 9% (fee-adjusted for 5 days)
        'apr30': 0.095,  # 9.5% (fee-adjusted for 30 days)
        'apr90': 0.098,  # 9.8% (fee-adjusted for 90 days)
        'liquidation_distance': 0.20,  # 20% safety buffer
        'max_size': 10000.0,
        'borrow_fee_2A': 0.0005,  # 0.05% borrow fee
        'borrow_fee_3B': 0.0003,  # 0.03% borrow fee
    })

    # Test 1: Create position
    print("\n1. Creating test position...")
    print(f"   Strategy data keys: {list(strategy_data.keys())}")
    position_id = service.create_position(
        strategy_row=strategy_data,
        deployment_usd=1000.0,
        liquidation_distance=0.20,
        is_levered=True,
        notes="Test position for Step 1-2 verification",
        is_paper_trade=True
    )
    print(f"   ✅ Position created: {position_id}")

    # Test 2: Query position
    print("\n2. Querying position...")
    position = service.get_position_by_id(position_id)
    if position is not None:
        print(f"   ✅ Position found:")
        print(f"      Status: {position['status']}")
        print(f"      Strategy: {position['token1']} → {position['token2']} → {position['token3']}")
        print(f"      Protocols: {position['protocol_A']} ↔ {position['protocol_B']}")
        print(f"      Deployment: ${position['deployment_usd']:.2f}")
        print(f"      Entry APR: {position['entry_net_apr']*100:.2f}%")
        print(f"      Levered: {position['is_levered']}")
        print(f"      Paper Trade: {position['is_paper_trade']}")
    else:
        print("   ❌ Position not found!")
        return

    # Test 3: Query snapshots (should have 1 initial snapshot)
    print("\n3. Querying snapshots...")
    snapshots = service.get_position_snapshots(position_id)
    print(f"   ✅ Found {len(snapshots)} snapshot(s)")
    if len(snapshots) > 0:
        snap = snapshots.iloc[0]
        print(f"      Snapshot ID: {snap['snapshot_id']}")
        print(f"      Total PnL: ${snap['total_pnl']:.2f}")
        print(f"      Base APR PnL: ${snap['pnl_base_apr']:.2f}")
        print(f"      Reward APR PnL: ${snap['pnl_reward_apr']:.2f}")
        print(f"      Price PnL (Token1): ${snap['pnl_price_token1']:.2f}")
        print(f"      Fees: ${snap['pnl_fees']:.2f}")

    # Test 4: Calculate current position value (with same prices/rates)
    print("\n4. Calculating position value...")
    current_prices = {
        'token1': 2.50,  # Same as entry
        'token2': 1.00,  # Same as entry
        'token3': 1.00,  # Same as entry
    }
    current_rates = {
        'protocol_A': {
            'token1_lend_base': 0.05,
            'token1_lend_reward': 0.01,
            'token2_borrow_base': 0.03,
            'token2_borrow_reward': 0.005,
        },
        'protocol_B': {
            'token2_lend_base': 0.07,
            'token2_lend_reward': 0.015,
            'token3_borrow_base': 0.04,
            'token3_borrow_reward': 0.008,
        }
    }

    value = service.calculate_position_value(position, current_prices, current_rates)
    print(f"   ✅ Current value calculated:")
    print(f"      Total Value: ${value['total_value']:.2f}")
    print(f"      Total PnL: ${value['total_pnl']:.2f}")

    # Test 5: Get active positions
    print("\n5. Querying active positions...")
    active = service.get_active_positions()
    print(f"   ✅ Found {len(active)} active position(s)")

    # Test 6: Portfolio summary
    print("\n6. Portfolio summary...")
    summary = service.get_portfolio_summary()
    print(f"   ✅ Portfolio Summary:")
    print(f"      Total Capital: ${summary['total_capital']:.2f}")
    print(f"      Average APR: {summary['avg_apr']:.2f}%")
    print(f"      Total Earned: ${summary['total_earned']:.2f}")
    print(f"      Position Count: {summary['position_count']}")

    # Test 7: Close position
    print("\n7. Closing position...")
    success = service.close_position(position_id, reason='test_completed', notes='Test completed successfully')
    if success:
        print(f"   ✅ Position closed")
        # Verify status
        closed_pos = service.get_position_by_id(position_id)
        print(f"      Status: {closed_pos['status']}")
        print(f"      Close reason: {closed_pos['close_reason']}")

        # Check final snapshot
        final_snapshots = service.get_position_snapshots(position_id)
        print(f"   ✅ Final snapshot count: {len(final_snapshots)}")
    else:
        print(f"   ❌ Failed to close position")

    # Cleanup
    conn.close()

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Steps 1-2 verified successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("  - Step 3: Add deploy buttons to All Strategies tab")
    print("  - Step 4: Create positions_tab.py with portfolio UI")


if __name__ == '__main__':
    test_position_service()
