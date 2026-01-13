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
