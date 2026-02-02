#!/usr/bin/env python3
"""Debug script to check why position 8cfcd054 is not being flagged for rebalancing"""

from analysis.position_service import PositionService
from analysis.position_calculator import PositionCalculator
import sqlite3
import config.settings as settings
from datetime import datetime

conn = sqlite3.connect(settings.SQLITE_PATH)
cursor = conn.cursor()

# Get position 8cfcd054
position_id = '8cfcd054-d0a9-4aa0-adbd-d5ddd2c8b258'
cursor.execute('SELECT * FROM positions WHERE position_id = ?', (position_id,))
cols = [desc[0] for desc in cursor.description]
row = cursor.fetchone()
position = dict(zip(cols, row))

# Get latest market data
cursor.execute('SELECT MAX(timestamp) FROM rates_snapshot')
latest_ts = cursor.fetchone()[0]
latest_seconds = int(datetime.fromisoformat(latest_ts.replace(' ', 'T')).timestamp())

print(f'Position: {position_id[:8]}')
print(f'Token2: {position["token2"]}')
print(f'Protocol A: {position["protocol_A"]}, Protocol B: {position["protocol_B"]}')
print(f'Entry timestamp: {position["entry_timestamp"]}')
print(f'Latest market data: {latest_ts}')
print()

# Get market data for all legs
cursor.execute('''
SELECT protocol, token, price_usd, collateral_ratio, liquidation_threshold, borrow_weight
FROM rates_snapshot
WHERE timestamp = ? AND (
    (protocol = ? AND token_contract = ?) OR
    (protocol = ? AND token_contract = ?) OR
    (protocol = ? AND token_contract = ?) OR
    (protocol = ? AND token_contract = ?)
)
''', (
    latest_ts,
    position['protocol_A'], position['token1_contract'],  # Leg 1A
    position['protocol_A'], position['token2_contract'],  # Leg 2A
    position['protocol_B'], position['token2_contract'],  # Leg 2B
    position['protocol_B'], position['token3_contract'],  # Leg 3B
))

market_data = cursor.fetchall()
print(f'Market data rows found: {len(market_data)}')
for row in market_data:
    print(f'  {row}')
print()

# Calculate liquidation distances
calculator = PositionCalculator()
deployment = float(position['deployment_usd'])
L_A = float(position['L_A'])
B_A = float(position['B_A'])
L_B = float(position['L_B'])
B_B = float(position['B_B'])

# Get current prices
cursor.execute('SELECT price_usd FROM rates_snapshot WHERE timestamp = ? AND protocol = ? AND token_contract = ?',
               (latest_ts, position['protocol_A'], position['token1_contract']))
price_1A_current = cursor.fetchone()[0]

cursor.execute('SELECT price_usd FROM rates_snapshot WHERE timestamp = ? AND protocol = ? AND token_contract = ?',
               (latest_ts, position['protocol_A'], position['token2_contract']))
price_2A_current = cursor.fetchone()[0]

cursor.execute('SELECT price_usd, liquidation_threshold FROM rates_snapshot WHERE timestamp = ? AND protocol = ? AND token_contract = ?',
               (latest_ts, position['protocol_B'], position['token2_contract']))
row_2B = cursor.fetchone()
price_2B_current = row_2B[0]
lltv_2B = row_2B[1]

cursor.execute('SELECT price_usd FROM rates_snapshot WHERE timestamp = ? AND protocol = ? AND token_contract = ?',
               (latest_ts, position['protocol_B'], position['token3_contract']))
price_3B_current = cursor.fetchone()[0]

print(f'Entry prices:')
print(f'  1A (token1={position["token1"]}): ${float(position["entry_price_1A"]):.6f}')
print(f'  2A (token2={position["token2"]}): ${float(position["entry_price_2A"]):.6f}')
print(f'  2B (token2={position["token2"]}): ${float(position["entry_price_2B"]):.6f}')
print(f'  3B (token3={position["token3"]}): ${float(position["entry_price_3B"]):.6f}')
print()
print(f'Current prices:')
print(f'  1A: ${price_1A_current}')
print(f'  2A: ${price_2A_current}')
print(f'  2B: ${price_2B_current}')
print(f'  3B: ${price_3B_current}')
print()

# Calculate baseline liquidation distance for leg 2A (entry)
baseline_2A = calculator.calculate_liquidation_price(
    collateral_value=deployment * L_A,
    loan_value=deployment * B_A,
    lending_token_price=float(position['entry_price_1A']),
    borrowing_token_price=float(position['entry_price_2A']),
    lltv=float(position['entry_liquidation_threshold_1A']),
    side='borrowing',
    borrow_weight=float(position.get('entry_borrow_weight_2A', 1.0))
)
print(f'Leg 2A Baseline (entry): {baseline_2A["pct_distance"]:.4f} ({baseline_2A["pct_distance"]*100:.2f}%)')

# Calculate live liquidation distance for leg 2A
live_2A = calculator.calculate_liquidation_price(
    collateral_value=deployment * L_A,
    loan_value=deployment * B_A,
    lending_token_price=price_1A_current,
    borrowing_token_price=price_2A_current,
    lltv=float(position['entry_liquidation_threshold_1A']),
    side='borrowing',
    borrow_weight=float(position.get('entry_borrow_weight_2A', 1.0))
)
print(f'Leg 2A Live: {live_2A["pct_distance"]:.4f} ({live_2A["pct_distance"]*100:.2f}%)')
delta_2A = abs(baseline_2A['pct_distance']) - abs(live_2A['pct_distance'])
print(f'Leg 2A Delta: {delta_2A:.4f} ({delta_2A*100:.2f}%)')
print(f'Leg 2A Needs rebalance: {abs(delta_2A) >= 0.02}')
print()

# Calculate baseline liquidation distance for leg 2B (entry)
baseline_2B = calculator.calculate_liquidation_price(
    collateral_value=deployment * L_B,
    loan_value=deployment * B_B,
    lending_token_price=float(position['entry_price_2B']),
    borrowing_token_price=float(position['entry_price_3B']),
    lltv=float(position['entry_liquidation_threshold_2B']),
    side='lending',
    borrow_weight=float(position.get('entry_borrow_weight_3B', 1.0))
)
print(f'Leg 2B Baseline (entry): {baseline_2B["pct_distance"]:.4f} ({baseline_2B["pct_distance"]*100:.2f}%)')

# Calculate live liquidation distance for leg 2B
live_2B = calculator.calculate_liquidation_price(
    collateral_value=deployment * L_B,
    loan_value=deployment * B_B,
    lending_token_price=price_2B_current,
    borrowing_token_price=price_3B_current,
    lltv=lltv_2B,
    side='lending',
    borrow_weight=float(position.get('entry_borrow_weight_3B', 1.0))
)
print(f'Leg 2B Live: {live_2B["pct_distance"]:.4f} ({live_2B["pct_distance"]*100:.2f}%)')
delta_2B = abs(baseline_2B['pct_distance']) - abs(live_2B['pct_distance'])
print(f'Leg 2B Delta: {delta_2B:.4f} ({delta_2B*100:.2f}%)')
print(f'Leg 2B Needs rebalance: {abs(delta_2B) >= 0.02}')
print()

print(f'OVERALL: Position needs rebalancing: {abs(delta_2A) >= 0.02 or abs(delta_2B) >= 0.02}')
