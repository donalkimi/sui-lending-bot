#!/usr/bin/env python3
"""
Debug script to test Slack Workflow variable sending
"""

import sys
import json
import requests
sys.path.insert(0, '.')

from config import settings
from alerts.slack_notifier import SlackNotifier

print("="*80)
print("SLACK WORKFLOW DEBUG TEST")
print("="*80)

# Check webhook URL
print(f"\n1. Webhook URL: {settings.SLACK_WEBHOOK_URL}")
is_workflow = '/workflows/' in settings.SLACK_WEBHOOK_URL or '/triggers/' in settings.SLACK_WEBHOOK_URL
print(f"   Is workflow webhook: {is_workflow}")

# Create test data
test_strategy = {
    'net_apr': 15.5,
    'leverage': 1.09,
    'token1': 'USDY',
    'token2': 'DEEP',
    'protocol_A': 'NAVI',
    'protocol_B': 'SuiLend',
    'L_A': 1.09,
    'B_A': 0.63,
    'L_B': 0.63,
    'B_B': 0.09,
    'lend_rate_1A': 9.7,
    'borrow_rate_2A': 19.5,
    'lend_rate_2B': 31.0,
    'borrow_rate_1B': 5.9
}

print("\n2. Test Strategy Data:")
for key, value in test_strategy.items():
    print(f"   {key}: {value}")

# Prepare variables (same as bot does)
variables = {
    "net_apr": f"{test_strategy['net_apr']:.2f}",
    "leverage": f"{test_strategy['leverage']:.2f}",
    "token1": test_strategy['token1'],
    "token2": test_strategy['token2'],
    "protocol_A": test_strategy['protocol_A'],
    "protocol_B": test_strategy['protocol_B'],
    "lend_amount": f"{test_strategy['L_A']:.2f}",
    "borrow_amount_1": f"{test_strategy['B_A']:.2f}",
    "lend_amount_2": f"{test_strategy['L_B']:.2f}",
    "borrow_amount_2": f"{test_strategy['B_B']:.2f}",
    "lend_rate_1A": f"{test_strategy['lend_rate_1A']:.2f}",
    "borrow_rate_2A": f"{test_strategy['borrow_rate_2A']:.2f}",
    "lend_rate_2B": f"{test_strategy['lend_rate_2B']:.2f}",
    "borrow_rate_1B": f"{test_strategy['borrow_rate_1B']:.2f}",
    "timestamp": "2024-12-17 TEST"
}

print("\n3. Variables Being Sent:")
for key, value in variables.items():
    print(f"   {key}: {value}")

# Test direct API call
print("\n4. Testing Direct API Call...")
print(f"   Sending to: {settings.SLACK_WEBHOOK_URL}")

payload = variables if is_workflow else {"text": "Test message", "blocks": []}
print(f"\n   Payload:")
print(f"   {json.dumps(payload, indent=2)}")

try:
    response = requests.post(
        settings.SLACK_WEBHOOK_URL,
        data=json.dumps(payload),
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"\n5. Response:")
    print(f"   Status Code: {response.status_code}")
    print(f"   Response Text: {response.text}")
    
    if response.status_code == 200:
        print("\n   ✓ API call successful!")
    else:
        print(f"\n   ✗ API call failed")
        
except Exception as e:
    print(f"\n   ✗ Error: {e}")

# Test using SlackNotifier class
print("\n" + "="*80)
print("6. Testing with SlackNotifier class...")
print("="*80)

notifier = SlackNotifier()
result = notifier.alert_high_apr(test_strategy)

print(f"\n   Result: {'✓ Success' if result else '✗ Failed'}")

print("\n" + "="*80)
print("CHECK YOUR SLACK CHANNEL NOW!")
print("="*80)
print("\nIf variables are still empty, the issue is likely:")
print("1. Variable names in Slack Workflow don't match exactly")
print("2. Workflow webhook expects different format")
print("3. Variables weren't added properly in Slack Workflow")
