"""
Slack notification system for alerts
"""

import requests
import json
from datetime import datetime
from typing import Dict, List
import sys
import os
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings


def format_usd_abbreviated(value: float) -> str:
    """Format USD amount abbreviated (e.g., $1.23M, $456K)"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    if value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value/1_000:.1f}K"
    else:
        return f"${value:.0f}"


def format_max_size_millions(value: float) -> str:
    """Format max size as millions with 2 decimal places (e.g., $1.80M)"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    return f"${value/1_000_000:.2f}M"


def format_strategy_summary_line(strategy: Dict, liq_dist: float) -> str:
    """
    Format a single strategy as a summary line

    Format: TOKEN1 → TOKEN2 → TOKEN3 | PROTOCOL_A ↔ PROTOCOL_B | Max Size $X.XXM | XX.XX%->XX.XX% (unlev->lev)

    Args:
        strategy: Dictionary with strategy details (can be DataFrame row dict)
        liq_dist: Liquidation distance as decimal (e.g., 0.20 for 20%)

    Returns:
        Formatted summary line string
    """
    token1 = strategy['token1']
    token2 = strategy['token2']
    token3 = strategy['token3']
    protocol_A = strategy['protocol_A']
    protocol_B = strategy['protocol_B']
    net_apr = strategy['net_apr']
    unlevered_apr = strategy.get('unlevered_apr', net_apr)  # Fallback to net_apr if not available
    max_size = strategy.get('max_size')

    # Format max size
    max_size_str = format_max_size_millions(max_size)

    return f"{token1} → {token2} → {token3} | {protocol_A} ↔ {protocol_B} | Max Size {max_size_str} | {unlevered_apr:.2f}%->{net_apr:.2f}% (unlev->lev)"


class SlackNotifier:
    """Send alerts to Slack"""
    
    def __init__(self, webhook_url: str = None):
        """
        Initialize Slack notifier
        
        Args:
            webhook_url: Slack webhook URL (default from settings)
        """
        self.webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL
        
    def send_message(self, message: str, blocks: List[Dict] = None, variables: Dict = None) -> bool:
        """
        Send a message to Slack
        
        Args:
            message: Plain text message (fallback)
            blocks: Slack blocks for rich formatting (for classic webhooks)
            variables: Dictionary of variables for Slack Workflows
            
        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url or self.webhook_url == "YOUR_SLACK_WEBHOOK_URL_HERE":
            print("⚠️  Slack webhook not configured. Set SLACK_WEBHOOK_URL in config/settings.py")
            return False
        
        try:
            # Check if this is a Slack Workflow webhook (contains '/workflows/' or '/triggers/')
            is_workflow = '/workflows/' in self.webhook_url or '/triggers/' in self.webhook_url
            
            if is_workflow and variables:
                # For Slack Workflows, send variables directly
                payload = variables
            else:
                # For classic Incoming Webhooks, use text/blocks
                payload = {"text": message}
                if blocks:
                    payload["blocks"] = blocks
            
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"✓ Slack notification sent")
                return True
            else:
                print(f"✗ Slack notification failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Error sending Slack notification: {e}")
            return False
    
    def alert_high_apr(self, strategy: Dict) -> bool:
        """
        Alert when a high APR opportunity is found
        
        Args:
            strategy: Dictionary with strategy details
            
        Returns:
            True if successful
        """
        message = f"🚀 High APR Opportunity: {strategy['net_apr']:.2f}%"
        
        # Prepare variables for Slack Workflows
        has_conversion = strategy['token1'] != strategy['token3']
        conversion_note = f" → {strategy['token1']}" if has_conversion else ""
        
        variables = {
            "net_apr": f"{strategy['net_apr']:.2f}",
            "liquidation_distance": f"{strategy['liquidation_distance']:.0f}",
            "token1": strategy['token1'],
            "token2": strategy['token2'],
            "token3": strategy['token3'],
            "conversion_note": conversion_note,
            "protocol_A": strategy['protocol_A'],
            "protocol_B": strategy['protocol_B'],
            "lend_amount": f"{strategy['L_A']:.2f}",
            "borrow_amount_1": f"{strategy['B_A']:.2f}",
            "lend_amount_2": f"{strategy['L_B']:.2f}",
            "borrow_amount_2": f"{strategy['B_B']:.2f}",
            "lend_rate_1A": f"{strategy['lend_rate_1A']:.2f}",
            "borrow_rate_2A": f"{strategy['borrow_rate_2A']:.2f}",
            "lend_rate_2B": f"{strategy['lend_rate_2B']:.2f}",
            "borrow_rate_3B": f"{strategy['borrow_rate_3B']:.2f}",
            "available_borrow_2A": format_usd_abbreviated(strategy.get('available_borrow_2A')),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        # Blocks for classic Incoming Webhooks (backwards compatibility)
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚀 High APR Opportunity Found!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Net APR:*\n{strategy['net_apr']:.2f}%"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Liquidation Distance:*\n{strategy['liquidation_distance']:.0f}%"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Token Pair:*\n{strategy['token1']} <-> {strategy['token2']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Protocols:*\n{strategy['protocol_A']} <-> {strategy['protocol_B']}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Strategy:*\n"
                        f"• Lend {strategy['L_A']:.2f} {strategy['token1']} in {strategy['protocol_A']} @ {strategy['lend_rate_1A']:.2f}%\n"
                        f"• Borrow {strategy['B_A']:.2f} {strategy['token2']} from {strategy['protocol_A']} @ {strategy['borrow_rate_2A']:.2f}%\n"
                        f"• Lend {strategy['L_B']:.2f} {strategy['token2']} in {strategy['protocol_B']} @ {strategy['lend_rate_2B']:.2f}%\n"
                        f"• Borrow {strategy['B_B']:.2f} {strategy['token3']} from {strategy['protocol_B']} @ {strategy['borrow_rate_3B']:.2f}%\n"
                        + (f"• Convert {strategy['token3']} → {strategy['token1']} (1:1)" if has_conversion else "")
                    )
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ]
        
        return self.send_message(message, blocks, variables)

    def alert_top_strategies(
        self,
        all_results,  # pd.DataFrame
        liquidation_distance: float = 0.20,
        deployment_usd: float = 100.0,
        timestamp: datetime = None
    ) -> bool:
        """
        Alert with top 3 strategies in two configurations

        Args:
            all_results: DataFrame of all analyzed strategies
            liquidation_distance: Liq dist % for display (default 20%)
            deployment_usd: Min deployment size filter (default 100)
            timestamp: Timestamp for the data snapshot (default: now)

        Returns:
            True if successful
        """
        import pandas as pd

        if timestamp is None:
            timestamp = datetime.now()

        # Filter Set 1: Unrestricted (only deployment size filter)
        filtered_set1 = all_results[
            (all_results['max_size'].notna()) &
            (all_results['max_size'] >= deployment_usd)
        ].head(3)

        # Filter Set 2: USDC-Only (token1=USDC, token3=token1, deployment filter)
        filtered_set2 = all_results[
            (all_results['token1'] == 'USDC') &
            (all_results['token3'] == all_results['token1']) &
            (all_results['max_size'].notna()) &
            (all_results['max_size'] >= deployment_usd)
        ].head(3)

        # Build formatted lines for Set 1
        set1_lines = []
        for _, row in filtered_set1.iterrows():
            line = format_strategy_summary_line(row.to_dict(), liquidation_distance)
            set1_lines.append(line)

        # Build formatted lines for Set 2
        set2_lines = []
        for _, row in filtered_set2.iterrows():
            line = format_strategy_summary_line(row.to_dict(), liquidation_distance)
            set2_lines.append(line)

        # Prepare variables for Slack Workflow
        liq_dist_pct = int(liquidation_distance * 100)
        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
        variables = {
            "liq_dist": str(liq_dist_pct),
            "timestamp": timestamp_str,
            "set1_count": str(len(set1_lines)),
            "set1_line1": set1_lines[0] if len(set1_lines) > 0 else "",
            "set1_line2": set1_lines[1] if len(set1_lines) > 1 else "",
            "set1_line3": set1_lines[2] if len(set1_lines) > 2 else "",
            "set2_count": str(len(set2_lines)),
            "set2_line1": set2_lines[0] if len(set2_lines) > 0 else "",
            "set2_line2": set2_lines[1] if len(set2_lines) > 1 else "",
            "set2_line3": set2_lines[2] if len(set2_lines) > 2 else "",
        }

        # Build fallback message for classic webhooks
        message_lines = [
            f"🚀 Top Lending Strategies",
            f"📅 {timestamp_str}",
            ""
        ]

        message_lines.append("📊 All Strategies (Top 3):")
        if set1_lines:
            for i, line in enumerate(set1_lines, 1):
                message_lines.append(f"{i}. {line}")
        else:
            message_lines.append("No strategies found")

        message_lines.append("")
        message_lines.append("💰 USDC-Only Strategies (Top 3):")
        if set2_lines:
            for i, line in enumerate(set2_lines, 1):
                message_lines.append(f"{i}. {line}")
        else:
            message_lines.append("No strategies found")

        message = "\n".join(message_lines)

        return self.send_message(message, blocks=None, variables=variables)

    def alert_rebalance_opportunity(
        self, 
        current_strategy: Dict,
        new_strategy: Dict,
        apr_improvement: float
    ) -> bool:
        """
        Alert when a rebalance opportunity is detected
        
        Args:
            current_strategy: Current position details
            new_strategy: Recommended new position
            apr_improvement: APR improvement in percentage points
            
        Returns:
            True if successful
        """
        message = f"🔄 Rebalance Opportunity: +{apr_improvement:.2f}% APR"
        
        # Variables for Slack Workflows
        variables = {
            "apr_improvement": f"{apr_improvement:.2f}",
            "current_apr": f"{current_strategy['net_apr']:.2f}",
            "new_apr": f"{new_strategy['net_apr']:.2f}",
            "current_token1": current_strategy['token1'],
            "current_token2": current_strategy['token2'],
            "current_protocol_A": current_strategy['protocol_A'],
            "current_protocol_B": current_strategy['protocol_B'],
            "new_token1": new_strategy['token1'],
            "new_token2": new_strategy['token2'],
            "new_protocol_A": new_strategy['protocol_A'],
            "new_protocol_B": new_strategy['protocol_B'],
            "liquidation_distance": f"{new_strategy['liquidation_distance']:.0f}",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        # Blocks for classic webhooks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔄 Rebalance Opportunity Detected",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*APR Improvement:* +{apr_improvement:.2f}% ({current_strategy['net_apr']:.2f}% → {new_strategy['net_apr']:.2f}%)"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Current:*\n{current_strategy['token1']} <-> {current_strategy['token2']}\n{current_strategy['protocol_A']} <-> {current_strategy['protocol_B']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Recommended:*\n{new_strategy['token1']} <-> {new_strategy['token2']}\n{new_strategy['protocol_A']} <-> {new_strategy['protocol_B']}"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ]
        
        return self.send_message(message, blocks, variables)
    
    def alert_error(self, error_message: str) -> bool:
        """
        Alert when an error occurs
        
        Args:
            error_message: Description of the error
            
        Returns:
            True if successful
        """
        message = f"⚠️ Bot Error: {error_message}"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚠️ Bot Error",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{error_message}```"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Occurred at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ]
        
        return self.send_message(message, blocks)


# Example usage
if __name__ == "__main__":
    notifier = SlackNotifier()
    
    # Test alert
    example_strategy = {
        'token1': 'USDY',
        'token2': 'DEEP',
        'protocol_A': 'NAVI',
        'protocol_B': 'SuiLend',
        'net_apr': 15.5,
        'leverage': 1.09,
        'L_A': 1.09,
        'B_A': 0.63,
        'L_B': 0.63,
        'B_B': 0.09,
        'lend_rate_1A': 9.7,
        'borrow_rate_2A': 19.5,
        'lend_rate_2B': 31.0,
        'borrow_rate_1B': 5.9
    }
    
    print("Sending test alert...")
    notifier.alert_high_apr(example_strategy)
