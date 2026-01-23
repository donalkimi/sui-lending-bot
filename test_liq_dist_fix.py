#!/usr/bin/env python3
"""
Test to verify the liquidation distance boundary transformation fix.
"""

from analysis.position_calculator import PositionCalculator

def test_liq_dist_transformation():
    """Test that user input is correctly transformed to liq_max"""
    print("Testing liquidation distance boundary transformation...")
    print("=" * 70)

    # Test case: User requests 20% minimum protection
    user_liq_dist = 0.20
    print(f"\nUser Input: {user_liq_dist * 100:.0f}% minimum liquidation distance")

    calc = PositionCalculator(liquidation_distance=user_liq_dist)

    # Verify internal transformation
    # liq_max = 0.20 / (1 - 0.20) = 0.25
    expected_liq_max = user_liq_dist / (1 - user_liq_dist)
    print(f"Original user input stored: {calc.liq_dist_input:.4f} (expected: {user_liq_dist:.4f})")
    print(f"Internal liq_max: {calc.liq_dist:.4f} (expected: {expected_liq_max:.4f})")
    assert abs(calc.liq_dist_input - user_liq_dist) < 0.0001, \
        f"Expected liq_dist_input={user_liq_dist}, got {calc.liq_dist_input}"
    assert abs(calc.liq_dist - expected_liq_max) < 0.0001, \
        f"Expected liq_max={expected_liq_max}, got {calc.liq_dist}"
    print("✓ Transformation correct")
    print("✓ Original input preserved")

    # Test with LLTV = 0.70
    LLTV = 0.70
    positions = calc.calculate_positions(
        collateral_ratio_A=LLTV,
        collateral_ratio_B=LLTV
    )

    # Verify r_A and r_B (using existing formula with liq_max)
    # r = 0.70 / (1 + 0.25) = 0.70 / 1.25 = 0.56
    expected_r = LLTV / (1 + calc.liq_dist)
    print(f"\nPosition ratio r: {positions['r_A']:.4f} (expected: {expected_r:.4f})")
    assert abs(positions['r_A'] - expected_r) < 0.0001, \
        f"Expected {expected_r}, got {positions['r_A']}"
    assert abs(positions['r_B'] - expected_r) < 0.0001, \
        f"Expected {expected_r}, got {positions['r_B']}"
    print("✓ Position ratios correct")

    # Calculate actual liquidation distances
    lending_dist = 1 - (positions['r_A'] / LLTV)
    borrowing_dist = (LLTV / positions['r_A']) - 1

    print(f"\nActual Liquidation Distances:")
    print(f"  Lending side:   {lending_dist * 100:.2f}% (should match user input: {user_liq_dist * 100:.0f}%)")
    print(f"  Borrowing side: {borrowing_dist * 100:.2f}% (liq_max)")

    assert abs(lending_dist - user_liq_dist) < 0.0001, \
        f"Lending distance should be {user_liq_dist}, got {lending_dist}"
    assert abs(borrowing_dist - expected_liq_max) < 0.0001, \
        f"Borrowing distance should be {expected_liq_max}, got {borrowing_dist}"

    # Verify that positions dict returns the original user input (for display)
    print(f"\nPosition result liquidation_distance: {positions['liquidation_distance'] * 100:.2f}%")
    assert abs(positions['liquidation_distance'] - user_liq_dist) < 0.0001, \
        f"Position liquidation_distance should be user input {user_liq_dist}, got {positions['liquidation_distance']}"

    print("\n✓ Lending side matches user's minimum request!")
    print("✓ Borrowing side gets bonus protection!")
    print("✓ Position dict returns original user input for display!")
    print("\n" + "=" * 70)
    print("SUCCESS: Boundary transformation verified!")
    print("=" * 70)


def test_multiple_values():
    """Test with multiple liquidation distance values"""
    print("\n\nTesting multiple liquidation distance values...")
    print("=" * 70)
    print(f"{'User Input':<15} {'Lending Dist':<15} {'Borrowing Dist (liq_max)':<25}")
    print("-" * 70)

    test_cases = [0.10, 0.15, 0.20, 0.25, 0.30]
    LLTV = 0.70

    for user_liq_dist in test_cases:
        calc = PositionCalculator(liquidation_distance=user_liq_dist)
        positions = calc.calculate_positions(
            collateral_ratio_A=LLTV,
            collateral_ratio_B=LLTV
        )

        lending_dist = 1 - (positions['r_A'] / LLTV)
        borrowing_dist = (LLTV / positions['r_A']) - 1

        print(f"{user_liq_dist * 100:>6.1f}%         {lending_dist * 100:>6.2f}%         {borrowing_dist * 100:>6.2f}%")

        # Verify lending matches user input
        assert abs(lending_dist - user_liq_dist) < 0.0001, \
            f"For input {user_liq_dist}, lending distance should be {user_liq_dist}, got {lending_dist}"

    print("-" * 70)
    print("✓ All test cases passed!")
    print("=" * 70)


if __name__ == "__main__":
    test_liq_dist_transformation()
    test_multiple_values()
    print("\n🎉 All tests passed! The quick fix is working correctly.")
