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
import pandas as pd  # ADDED: Required for DataFrame operations

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from utils.time_helpers import to_datetime_str  # ADDED: CRITICAL - required for timestamp formatting


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

    Format: TOKEN1 → TOKEN2 → TOKEN3 | PROTOCOL_A ↔ PROTOCOL_B | Max Size $X.XXM | 🟢 Net APR XX.XX% | 🟢 5day APR XX.XX%

    Args:
        strategy: Dictionary with strategy details (can be DataFrame row dict)
        liq_dist: Liquidation distance as decimal (e.g., 0.20 for 20%)

    Returns:
        Formatted summary line string
    """
    token1 = strategy['token1']
    token2 = strategy['token2']
    token3 = strategy['token3']
    protocol_a = strategy['protocol_a']
    protocol_b = strategy['protocol_b']
    max_size = strategy.get('max_size')

    # Format max size
    max_size_str = format_max_size_millions(max_size)

    # Get APR values (levered)
    net_apr_value = strategy.get('apr_net', strategy.get('net_apr', 0))
    apr5_value = strategy.get('apr5', strategy.get('net_apr', 0))

    # Determine emoji indicators based on positive/negative values
    net_apr_indicator = "🟢" if net_apr_value >= 0 else "🔴"
    apr5_indicator = "🟢" if apr5_value >= 0 else "🔴"

    # Build token flow (levered)
    token_flow = f"{token1} → {token2} → {token3}"

    return f"{token_flow} | {protocol_a} ↔ {protocol_b} | Max Size {max_size_str} | {net_apr_indicator} Net APR {net_apr_value * 100:.2f}% | {apr5_indicator} 5day APR {apr5_value * 100:.2f}%"


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
        Send a message to Slack with retry logic and timeout

        Args:
            message: Plain text message (fallback)
            blocks: Slack blocks for rich formatting (for classic webhooks)
            variables: Dictionary of variables for Slack Workflows

        Returns:
            True if successful, False otherwise
        """
        import time
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        if not self.webhook_url or self.webhook_url == "YOUR_SLACK_WEBHOOK_URL_HERE":
            print("⚠️  Slack webhook not configured. Set SLACK_WEBHOOK_URL in config/settings.py")
            return False

        # Check if this is a Slack Workflow webhook (contains '/workflows/' or '/triggers/')
        is_workflow = '/workflows/' in self.webhook_url or '/triggers/' in self.webhook_url

        print(f"[DEBUG] Webhook URL check: is_workflow={is_workflow}")
        print(f"[DEBUG] Webhook URL contains: {self.webhook_url[:50]}...")
        print(f"[DEBUG] Variables received: {'None' if variables is None else f'{len(variables)} keys'}")

        # Build payload
        if is_workflow and variables:
            # For Slack Workflows, send variables directly
            payload = variables
            print(f"[DEBUG] ✅ Using workflow mode with variables")
            # Show first 3 variables as preview
            preview = {k: v[:50] if isinstance(v, str) and len(v) > 50 else v
                      for k, v in list(variables.items())[:3]}
            print(f"[DEBUG] Payload preview (first 3 vars): {json.dumps(preview, indent=2)}")
        elif is_workflow and not variables:
            # Workflow webhook requires variables but none provided
            print(f"[ERROR] ⚠️  Workflow webhook detected but variables is None - notification will fail")
            print(f"[ERROR] Falling back to error message")
            return False
        else:
            # For classic Incoming Webhooks, use text/blocks
            payload = {"text": message}
            print(f"[DEBUG] Using classic mode: is_workflow={is_workflow}")
            if blocks:
                payload["blocks"] = blocks

        print(f"[DEBUG] Final payload keys: {list(payload.keys())}")

        # Validate payload size
        payload_str = json.dumps(payload)
        payload_size = len(payload_str)
        print(f"[DEBUG] Payload size: {payload_size} bytes")

        if is_workflow and payload_size > 3000:
            print(f"[WARNING] Payload size ({payload_size} bytes) exceeds recommended limit (3000 bytes)")

        # Configure retry strategy for transient failures
        retry_strategy = Retry(
            total=3,  # Max 3 retries
            backoff_factor=1,  # Wait 1s, 2s, 4s between retries
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP codes
            allowed_methods=["POST"],  # Retry POST requests
            raise_on_status=False  # Don't raise exception on bad status
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        try:
            print(f"[DEBUG] Sending Slack notification (timeout=10s, max_retries=3)...")
            start_time = time.time()

            response = session.post(
                self.webhook_url,
                data=payload_str,
                headers={'Content-Type': 'application/json'},
                timeout=10  # 10 seconds timeout (connect + read)
            )

            elapsed = (time.time() - start_time) * 1000
            print(f"[DEBUG] Response received in {elapsed:.0f}ms: {response.status_code}")

            if response.status_code == 200:
                print(f"[OK] ✅ Slack notification sent successfully")
                return True
            else:
                print(f"[ERROR] ❌ Slack notification failed: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.Timeout as e:
            print(f"[ERROR] ⏱️  Slack notification timeout after 10s: {e}")
            print(f"[ERROR] This usually indicates network issues or Slack API is slow")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f"[ERROR] 🔌 Slack connection error: {e}")
            print(f"[ERROR] Check network connectivity and webhook URL")
            return False
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] 🌐 Slack request failed: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] ⚠️  Unexpected error sending Slack notification: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            session.close()
    
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
            "protocol_A": strategy['protocol_a'],
            "protocol_B": strategy['protocol_b'],
            "lend_amount": f"{strategy['l_a']:.2f}",
            "borrow_amount_1": f"{strategy['b_a']:.2f}",
            "lend_amount_2": f"{strategy['l_b']:.2f}",
            "borrow_amount_2": f"{strategy['b_b']:.2f}",
            "lend_rate_1A": f"{strategy['lend_rate_1a']:.2f}",
            "borrow_rate_2A": f"{strategy['borrow_rate_2a']:.2f}",
            "lend_rate_2B": f"{strategy['lend_rate_2b']:.2f}",
            "borrow_rate_3B": f"{strategy['borrow_rate_3b']:.2f}",
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
                        "text": f"*Protocols:*\n{strategy['protocol_a']} <-> {strategy['protocol_b']}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Strategy:*\n"
                        f"• Lend {strategy['l_a']:.2f} {strategy['token1']} in {strategy['protocol_a']} @ {strategy['lend_rate_1a']:.2f}%\n"
                        f"• Borrow {strategy['b_a']:.2f} {strategy['token2']} from {strategy['protocol_a']} @ {strategy['borrow_rate_2a']:.2f}%\n"
                        f"• Lend {strategy['l_b']:.2f} {strategy['token2']} in {strategy['protocol_b']} @ {strategy['lend_rate_2b']:.2f}%\n"
                        f"• Borrow {strategy['b_b']:.2f} {strategy['token3']} from {strategy['protocol_b']} @ {strategy['borrow_rate_3b']:.2f}%\n"
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
        all_results: pd.DataFrame,
        liquidation_distance: float,
        deployment_usd: float = 100.0,
        timestamp: int = None
    ) -> bool:
        """
        Alert top lending strategies across multiple categories
        
        Args:
            all_results: DataFrame of all analyzed strategies
            liquidation_distance: Liquidation distance as decimal (e.g., 0.20)
            deployment_usd: Deployment amount in USD (for filtering)
            timestamp: Unix timestamp in seconds
            
        Returns:
            True if successful
        """
        print(f"[DEBUG] alert_top_strategies called")
        print(f"[DEBUG] all_results shape: {all_results.shape if all_results is not None else 'None'}")
        print(f"[DEBUG] liquidation_distance: {liquidation_distance}")
        print(f"[DEBUG] timestamp: {timestamp}")
        
        if all_results is None or all_results.empty:
            print("[DEBUG] all_results is empty - calling alert_error")
            return self.alert_error("No valid strategies found in this refresh run.")
        
        # Initialize variables to None (will be set in try block)
        variables = None
        
        try:
            print(f"[DEBUG] Starting strategy filtering...")
            
            # Filter Set 1: All strategies (top 3 by net_apr)
            filtered_set1 = all_results.nlargest(3, 'net_apr')
            print(f"[DEBUG] Set 1 filtered: {len(filtered_set1)} strategies")
            
            # Filter Set 2: USDC-only strategies (top 3)
            filtered_set2 = all_results[
                (all_results['token1'] == 'USDC') &
                (all_results['token2'] == 'USDC') &
                (all_results['token3'] == 'USDC')
            ].nlargest(3, 'net_apr')
            print(f"[DEBUG] Set 2 filtered: {len(filtered_set2)} strategies")
            
            # Filter Set 3: Unlevered strategies (top 3)
            # Unlevered = simple lend/borrow with no recursion
            filtered_set3 = all_results[
                all_results.get('is_levered', True) == False
            ].nlargest(3, 'net_apr') if 'is_levered' in all_results.columns else pd.DataFrame()
            print(f"[DEBUG] Set 3 filtered: {len(filtered_set3)} strategies")
            
            # Build formatted lines for Set 1
            print(f"[DEBUG] Building Set 1 lines...")
            set1_lines = []
            for idx, row in filtered_set1.iterrows():
                line = format_strategy_summary_line(row.to_dict(), liquidation_distance)
                set1_lines.append(line)
                print(f"[DEBUG] Set1 line {len(set1_lines)}: {line[:80]}...")
            
            # Build formatted lines for Set 2
            print(f"[DEBUG] Building Set 2 lines...")
            set2_lines = []
            for idx, row in filtered_set2.iterrows():
                line = format_strategy_summary_line(row.to_dict(), liquidation_distance)
                set2_lines.append(line)
                print(f"[DEBUG] Set2 line {len(set2_lines)}: {line[:80] if line else 'EMPTY'}...")
            
            # Build formatted lines for Set 3
            print(f"[DEBUG] Building Set 3 lines...")
            set3_lines = []
            for idx, row in filtered_set3.iterrows():
                line = format_strategy_summary_line(row.to_dict(), liquidation_distance)
                set3_lines.append(line)
                print(f"[DEBUG] Set3 line {len(set3_lines)}: {line[:80] if line else 'EMPTY'}...")
            
            print(f"[DEBUG] All line sets built: set1={len(set1_lines)}, set2={len(set2_lines)}, set3={len(set3_lines)}")
            
            # Prepare variables for Slack Workflow
            print(f"[DEBUG] Creating variables dict...")
            liq_dist_pct = int(liquidation_distance * 100)
            print(f"[DEBUG] liq_dist_pct={liq_dist_pct}")
            
            timestamp_str = to_datetime_str(timestamp) + ' UTC'
            print(f"[DEBUG] timestamp_str={timestamp_str}")
            
            # Build formatted message with just the top strategy
            if set1_lines and len(set1_lines) > 0:
                formatted_message = f"{timestamp_str}: {set1_lines[0]}"
            else:
                formatted_message = f"{timestamp_str}: No strategies found"

            variables = {
                "liq_dist": str(liq_dist_pct),
                "timestamp": timestamp_str,
                "notification_text": formatted_message  # Renamed from "message" to avoid Slack conflicts
            }

            print(f"[DEBUG] ✅ Variables dict created with {len(variables)} keys (including 'notification_text')")
            print(f"[DEBUG] Sample variable values:")
            print(f"[DEBUG]   liq_dist: {variables['liq_dist']}")
            print(f"[DEBUG]   timestamp: {variables['timestamp']}")
            print(f"[DEBUG]   notification_text (first 100 chars): {formatted_message[:100]}...")

        except KeyError as e:
            print(f"[ERROR] ❌ Missing key in strategy data: {e}")
            print(f"[ERROR] Available DataFrame columns: {list(all_results.columns) if hasattr(all_results, 'columns') else 'N/A'}")
            import traceback
            traceback.print_exc()
            variables = None
            formatted_message = None
        except AttributeError as e:
            print(f"[ERROR] ❌ Attribute error building variables: {e}")
            print(f"[ERROR] all_results type: {type(all_results)}")
            import traceback
            traceback.print_exc()
            variables = None
            formatted_message = None
        except Exception as e:
            print(f"[ERROR] ❌ Unexpected exception building variables dict: {e}")
            print(f"[ERROR] Exception type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            variables = None
            formatted_message = None

        # Use formatted message or build fallback
        if formatted_message:
            message = formatted_message
        else:
            # Fallback if message creation failed
            timestamp_str_fallback = to_datetime_str(timestamp) + ' UTC' if timestamp else 'N/A'
            message = f"🚀 Top Lending Strategies\n📅 {timestamp_str_fallback}\n\nNo strategies available"

        print(f"[DEBUG] About to call send_message with variables={'None' if variables is None else f'{len(variables)} keys'}")

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
            "current_protocol_A": current_strategy['protocol_a'],
            "current_protocol_B": current_strategy['protocol_b'],
            "new_token1": new_strategy['token1'],
            "new_token2": new_strategy['token2'],
            "new_protocol_A": new_strategy['protocol_a'],
            "new_protocol_B": new_strategy['protocol_b'],
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
                        "text": f"*Current:*\n{current_strategy['token1']} <-> {current_strategy['token2']}\n{current_strategy['protocol_a']} <-> {current_strategy['protocol_b']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Recommended:*\n{new_strategy['token1']} <-> {new_strategy['token2']}\n{new_strategy['protocol_a']} <-> {new_strategy['protocol_b']}"
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

    def alert_position_rebalanced(
        self,
        position_id: str,
        token1: str,
        token2: str,
        token3: str,
        protocol_a: str,
        protocol_b: str,
        liq_dist_2a_before: float,
        liq_dist_2a_after: float,
        liq_dist_2b_before: float,
        liq_dist_2b_after: float,
        rebalance_timestamp: int
    ) -> bool:
        """
        Alert when a position has been rebalanced.

        Sends a single-line notification with position details and liquidation distance changes.
        For recursive_lending strategy type (all positions have token3).

        Args:
            position_id: Full position UUID
            token1: First token symbol (lent at Protocol A)
            token2: Second token symbol (borrowed from A, lent to B)
            token3: Third token symbol (borrowed from B)
            protocol_a: First protocol name
            protocol_b: Second protocol name
            liq_dist_2a_before: Liquidation distance for token2 at protocol_a before rebalance
            liq_dist_2a_after: Liquidation distance for token2 at protocol_a after rebalance
            liq_dist_2b_before: Liquidation distance for token2 at protocol_b before rebalance
            liq_dist_2b_after: Liquidation distance for token2 at protocol_b after rebalance
            rebalance_timestamp: Unix timestamp of rebalance

        Returns:
            True if successful
        """
        from datetime import datetime

        # Format timestamp
        time_str = datetime.fromtimestamp(rebalance_timestamp).strftime('%H:%M:%S')

        # Format token flow (recursive_lending always has 3 tokens)
        token_flow = f"{token1}<->{token2}<->{token3}"

        # Format protocols
        protocols = f"{protocol_a}/{protocol_b}"

        # Helper function to format percentage with sign
        def fmt_pct(value):
            if value is None or (isinstance(value, float) and (value == float('inf') or value == float('-inf'))):
                return "N/A"
            return f"{value:+.1f}%"

        # Helper function to get delta indicator
        def get_delta(before, after):
            if before is None or after is None:
                return ""
            if isinstance(before, float) and (before == float('inf') or before == float('-inf')):
                return ""
            if isinstance(after, float) and (after == float('inf') or after == float('-inf')):
                return ""

            # Positive liquidation distance is good (further from liquidation)
            # If after > before, distance improved (safer)
            delta = after - before
            if abs(delta) < 0.5:  # Less than 0.5% change, no indicator
                return ""
            elif delta > 0:
                return " ✅"  # Improved (increased distance)
            else:
                return " ⚠️"  # Worsened (decreased distance)

        # Format leg 2A (token2 at protocol_a)
        leg_2a_label = f"{token2} in {protocol_a}"
        leg_2a_before = fmt_pct(liq_dist_2a_before * 100 if liq_dist_2a_before is not None else None)
        leg_2a_after = fmt_pct(liq_dist_2a_after * 100 if liq_dist_2a_after is not None else None)
        leg_2a_delta = get_delta(
            liq_dist_2a_before * 100 if liq_dist_2a_before is not None else None,
            liq_dist_2a_after * 100 if liq_dist_2a_after is not None else None
        )
        leg_2a_str = f"Liq Dist {leg_2a_label}: {leg_2a_before} → {leg_2a_after}{leg_2a_delta}"

        # Format leg 2B (token2 at protocol_b)
        leg_2b_label = f"{token2} in {protocol_b}"
        leg_2b_before = fmt_pct(liq_dist_2b_before * 100 if liq_dist_2b_before is not None else None)
        leg_2b_after = fmt_pct(liq_dist_2b_after * 100 if liq_dist_2b_after is not None else None)
        leg_2b_delta = get_delta(
            liq_dist_2b_before * 100 if liq_dist_2b_before is not None else None,
            liq_dist_2b_after * 100 if liq_dist_2b_after is not None else None
        )
        leg_2b_str = f" | {leg_2b_label}: {leg_2b_before} → {leg_2b_after}{leg_2b_delta}"

        # Build the main message line
        main_line = f"🔄 {time_str} | {token_flow} | {protocols} | {leg_2a_str}{leg_2b_str}"

        # Full message with Position ID on new line
        message = f"{main_line}\nPosition ID: {position_id}"

        # Variables for Slack Workflows
        variables = {
            "time": time_str,
            "position_id": position_id,
            "token_flow": token_flow,
            "protocols": protocols,
            "leg_2a_label": leg_2a_label,
            "leg_2a_before": leg_2a_before,
            "leg_2a_after": leg_2a_after,
            "leg_2b_label": leg_2b_label,
            "leg_2b_before": leg_2b_before,
            "leg_2b_after": leg_2b_after,
            "notification_text": message  # Renamed from "message" to avoid Slack conflicts
        }

        # Blocks for classic webhooks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔄 Position Rebalanced",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{token_flow}* | {protocols}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*{leg_2a_label}:*\n{leg_2a_before} → {leg_2a_after}{leg_2a_delta}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*{leg_2b_label}:*\n{leg_2b_before} → {leg_2b_after}{leg_2b_delta}"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Position ID: `{position_id}` | {time_str}"
                    }
                ]
            }
        ]

        return self.send_message(message, blocks, variables)


# Example usage
if __name__ == "__main__":
    notifier = SlackNotifier()
    
    # Test alert
    example_strategy = {
        'token1': 'USDY',
        'token2': 'DEEP',
        'token3': 'USDY',
        'protocol_a': 'NAVI',
        'protocol_b': 'SuiLend',
        'net_apr': 15.5,
        'liquidation_distance': 20,
        'leverage': 1.09,
        'l_a': 1.09,
        'b_a': 0.63,
        'l_b': 0.63,
        'b_b': 0.09,
        'lend_rate_1a': 9.7,
        'borrow_rate_2a': 19.5,
        'lend_rate_2b': 31.0,
        'borrow_rate_3b': 5.9
    }
    
    print("Sending test alert...")
    notifier.alert_high_apr(example_strategy)