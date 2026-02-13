# Slack Notifier Reference

## Overview

The Slack notifier system sends automated notifications to a configured Slack channel for key bot events. It uses **Slack Workflow webhooks** with variable-based messaging.

**File Location:** [`alerts/slack_notifier.py`](../alerts/slack_notifier.py)

---

## Architecture

### SlackNotifier Class

The main class that handles all Slack notifications:

```python
from alerts.slack_notifier import SlackNotifier

notifier = SlackNotifier()  # Uses SLACK_WEBHOOK_URL from settings
# OR
notifier = SlackNotifier(webhook_url="https://hooks.slack.com/...")
```

### Webhook Configuration

**Environment Variable:** `SLACK_WEBHOOK_URL`
**Location:** `config/settings.py`

**Webhook Type:** Slack Workflow Webhook (not classic Incoming Webhook)
- Workflow webhooks accept **variables** as JSON payload
- Variables are referenced in Slack Workflow as `{{ variable_name }}`

---

## Notification Types

The notifier supports **4 notification types**:

### 1. Top Strategies Alert

**Method:** `alert_top_strategies()`

**Triggered By:**
- [`data/refresh_pipeline.py`](../data/refresh_pipeline.py) - Line ~267
- Called when `send_slack_notifications=True`
- Sends after strategy analysis completes

**Message Format:**
```
{timestamp}: {best_strategy_line}
```

**Example:**
```
2026-02-13 14:32:15 UTC: USDC → DEEP → USDC | Navi ↔ Suilend | Max Size $1.23M | 🟢 Net APR 15.50% | 🟢 5day APR 14.20%
```

**Variables Sent to Slack:**
```json
{
  "liq_dist": "20",
  "timestamp": "2026-02-13 14:32:15 UTC",
  "notification_text": "{full message}"
}
```

**Strategy Line Format:**
```
{token1} → {token2} → {token3} | {protocol_a} ↔ {protocol_b} | Max Size ${X.XX}M | {indicator} Net APR {XX.XX}% | {indicator} 5day APR {XX.XX}%
```

Where:
- `{indicator}` = 🟢 (positive APR) or 🔴 (negative APR)
- Max Size is formatted as millions (e.g., $1.80M)
- APRs shown as percentages with 2 decimal places

---

### 2. Position Rebalanced Alert

**Method:** `alert_position_rebalanced()`

**Triggered By:**
- [`analysis/position_service.py`](../analysis/position_service.py) - Lines ~1330-1348
- Called automatically after successful rebalance
- Fires for both auto-rebalance (from `refresh_pipeline`) and manual rebalance (from dashboard)

**Message Format:**
```
🔄 {HH:MM:SS} | {token1}<->{token2}<->{token3} | {protocol_a}/{protocol_b} | Liq Dist {token2} in {protocol_a}: {before}% → {after}% {delta} | {token2} in {protocol_b}: {before}% → {after}% {delta}
Position ID: {full_position_id}
```

**Example:**
```
🔄 14:32:15 | USDC<->DEEP<->USDC | Navi/Suilend | Liq Dist DEEP in Navi: +28.5% → +32.1% ✅ | DEEP in Suilend: +45.2% → +48.8% ✅
Position ID: a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6
```

**Delta Indicators:**
- ✅ = Liquidation distance improved (increased by >0.5%)
- ⚠️ = Liquidation distance worsened (decreased by >0.5%)
- (none) = Change less than 0.5%

**Variables Sent to Slack:**
```json
{
  "time": "14:32:15",
  "position_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
  "token_flow": "USDC<->DEEP<->USDC",
  "protocols": "Navi/Suilend",
  "leg_2a_label": "DEEP in Navi",
  "leg_2a_before": "+28.5%",
  "leg_2a_after": "+32.1%",
  "leg_2b_label": "DEEP in Suilend",
  "leg_2b_before": "+45.2%",
  "leg_2b_after": "+48.8%",
  "notification_text": "{full message}"
}
```

**Liquidation Distance Explanation:**
- **2A** = Liquidation distance for token2 borrowed from Protocol A
- **2B** = Liquidation distance for token2 lent to Protocol B
- Shown as signed percentages (+28.5% means 28.5% above liquidation price)
- Higher (more positive) = safer from liquidation

---

### 3. High APR Alert

**Method:** `alert_high_apr()`

**Triggered By:**
- Currently **not actively used** in the codebase
- Can be manually called for opportunistic alerts

**Message Format:**
```
🚀 High APR Opportunity: {net_apr}%
```

**Variables Sent to Slack:**
```json
{
  "net_apr": "15.50",
  "liquidation_distance": "20",
  "token1": "USDC",
  "token2": "DEEP",
  "token3": "USDC",
  "conversion_note": "",
  "protocol_A": "Navi",
  "protocol_B": "Suilend",
  "lend_amount": "1.09",
  "borrow_amount_1": "0.63",
  "lend_amount_2": "0.63",
  "borrow_amount_2": "0.09",
  "lend_rate_1A": "9.70",
  "borrow_rate_2A": "19.50",
  "lend_rate_2B": "31.00",
  "borrow_rate_3B": "5.90",
  "available_borrow_2A": "$1.2M",
  "timestamp": "2026-02-13 14:32:15 UTC"
}
```

---

### 4. Error Alert

**Method:** `alert_error()`

**Triggered By:**
- [`data/refresh_pipeline.py`](../data/refresh_pipeline.py) - Various error handlers
- Called when critical failures occur (e.g., no strategies found, database errors)

**Message Format:**
```
⚠️ Bot Error: {error_message}
```

**Example:**
```
⚠️ Bot Error: No valid strategies found in this refresh run.
```

**Variables Sent to Slack:**
- **None** - Uses classic webhook format (text + blocks only)

---

## Call Flow Diagrams

### Top Strategies Notification

```
User runs: python send_top_strategies_to_slack.py
    ↓
refresh_pipeline(send_slack_notifications=True)
    ↓
Analyze strategies → rank by net_apr
    ↓
Get top strategy from all_results.nlargest(3, 'net_apr')
    ↓
SlackNotifier.alert_top_strategies(all_results, liquidation_distance, timestamp)
    ↓
Format message: "{timestamp}: {best_strategy_line}"
    ↓
send_message(message, blocks=None, variables={...})
    ↓
POST to SLACK_WEBHOOK_URL with JSON payload
    ↓
Slack Workflow receives variables → formats message → posts to channel
```

### Position Rebalanced Notification

```
Auto-rebalance triggered (liquidation distance delta > 5%)
    OR
Manual rebalance button clicked in dashboard
    ↓
PositionService.rebalance_position()
    ↓
Calculate "before" liquidation distances (opening state)
    ↓
Capture rebalance snapshot (includes "after" distances)
    ↓
Create rebalance record in database
    ↓
SlackNotifier.alert_position_rebalanced(position_id, tokens, protocols, liq_dists, timestamp)
    ↓
Format message with delta indicators (✅/⚠️)
    ↓
send_message(message, blocks=[...], variables={...})
    ↓
POST to SLACK_WEBHOOK_URL
    ↓
Slack Workflow posts formatted message to channel
```

---

## Implementation Details

### Message Formatting Helpers

**`format_strategy_summary_line(strategy, liq_dist)`**
- Location: [`slack_notifier.py:38-72`](../alerts/slack_notifier.py#L38-L72)
- Formats a single strategy as a one-line summary
- Handles max size abbreviation ($1.23M, $456K)
- Adds emoji indicators for positive/negative APRs

**`format_usd_abbreviated(value)`**
- Location: [`slack_notifier.py:19-28`](../alerts/slack_notifier.py#L19-L28)
- Formats large USD amounts as millions/thousands

**`format_max_size_millions(value)`**
- Location: [`slack_notifier.py:31-36`](../alerts/slack_notifier.py#L31-L36)
- Always formats as millions with 2 decimals

### Send Message Logic

**`send_message(message, blocks, variables)`**
- Location: [`slack_notifier.py:87-197`](../alerts/slack_notifier.py#L87-L197)

**Key Features:**
1. **Auto-detection of webhook type:**
   - Checks if URL contains `/workflows/` or `/triggers/`
   - Uses `variables` for Workflow webhooks
   - Falls back to `text`/`blocks` for classic webhooks

2. **Retry logic:**
   - Max 3 retries with exponential backoff (1s, 2s, 4s)
   - Retries on HTTP 429, 500, 502, 503, 504
   - 10 second timeout per request

3. **Payload validation:**
   - Checks payload size (warns if >3000 bytes for Workflows)
   - Validates webhook URL is configured

4. **Error handling:**
   - Graceful timeout handling
   - Connection error detection
   - Detailed debug logging

---

## Slack Workflow Setup

### Required Workflow Configuration

1. **Create Slack Workflow** in your workspace
2. **Add webhook trigger** → copy webhook URL
3. **Add variable inputs** for each notification type you want to support

### Variable Mapping for Top Strategies

Your Slack Workflow should accept these variables:

| Variable Name | Type | Description |
|---------------|------|-------------|
| `notification_text` | Text | The complete formatted message |
| `liq_dist` | Text | Liquidation distance percentage (e.g., "20") |
| `timestamp` | Text | Analysis timestamp |

**Example Workflow Step:**
```
Send message to channel: #sui_lending_bot
Message text: {{ notification_text }}
```

### Variable Mapping for Position Rebalanced

| Variable Name | Type | Description |
|---------------|------|-------------|
| `notification_text` | Text | The complete formatted message |
| `time` | Text | Rebalance time (HH:MM:SS) |
| `position_id` | Text | Full UUID |
| `token_flow` | Text | Token flow string (e.g., "USDC<->DEEP<->USDC") |
| `protocols` | Text | Protocol pair (e.g., "Navi/Suilend") |
| `leg_2a_label` | Text | Readable label for leg 2A (e.g., "DEEP in Navi") |
| `leg_2a_before` | Text | Before liquidation distance |
| `leg_2a_after` | Text | After liquidation distance |
| `leg_2b_label` | Text | Readable label for leg 2B |
| `leg_2b_before` | Text | Before liquidation distance |
| `leg_2b_after` | Text | After liquidation distance |

---

## Testing

### Manual Testing Scripts

**1. Send Top Strategies:**
```bash
python send_top_strategies_to_slack.py
```
- Runs full analysis pipeline
- Sends best strategy to Slack
- Located at project root

**2. Test All Notification Types:**
```bash
# Test rebalance notification only
python test_slack_notification.py --test rebalance

# Test strategies notification only
python test_slack_notification.py --test strategies

# Test error notification only
python test_slack_notification.py --test error

# Test all notifications
python test_slack_notification.py --test all
```

**Test script location:** [`test_slack_notification.py`](../test_slack_notification.py)

### Debug Logging

The notifier includes extensive debug logging:

```
[DEBUG] Webhook URL check: is_workflow=True
[DEBUG] Variables received: 3 keys
[DEBUG] ✅ Using workflow mode with variables
[DEBUG] Payload preview (first 3 vars): {...}
[DEBUG] Final payload keys: ['liq_dist', 'timestamp', 'notification_text']
[DEBUG] Payload size: 456 bytes
[DEBUG] Sending Slack notification (timeout=10s, max_retries=3)...
[DEBUG] Response received in 234ms: 200
[OK] ✅ Slack notification sent successfully
```

---

## Common Issues

### Issue: Notifications not received

**Check:**
1. `SLACK_WEBHOOK_URL` is set in `config/settings.py`
2. URL is not the placeholder `"YOUR_SLACK_WEBHOOK_URL_HERE"`
3. URL is a **Workflow webhook** (contains `/workflows/` or `/triggers/`)
4. Slack Workflow is configured to accept `notification_text` variable
5. Workflow is **enabled** in Slack

### Issue: "Payload too large" warning

**Cause:** Workflow webhooks have a ~3000 byte limit

**Solution:** Reduce message length or use classic webhook

### Issue: Rebalance notification not firing

**Check:**
1. `send_slack_notifications=True` in the call to `refresh_pipeline()`
2. Dashboard "Get Live Market Data" button has notifications enabled (line 165 in `streamlit_app.py`)
3. Notification errors are logged but don't block rebalance - check console output

### Issue: Variable name conflicts

**Avoid using:** `message` as a variable name (Slack reserved keyword)

**Use instead:** `notification_text` (already implemented)

---

## Code References

### Where Notifications Are Sent From

| Notification Type | Source File | Line(s) | Condition |
|-------------------|-------------|---------|-----------|
| Top Strategies | `data/refresh_pipeline.py` | ~267 | `send_slack_notifications=True` |
| Position Rebalanced | `analysis/position_service.py` | ~1330-1348 | After successful rebalance |
| Error (no strategies) | `data/refresh_pipeline.py` | ~269 | No valid strategies found |

### Where Notifications Are Configured

| Item | File | Location |
|------|------|----------|
| Webhook URL | `config/settings.py` | `SLACK_WEBHOOK_URL` env var |
| Rebalance threshold | `config/settings.py` | `REBALANCE_THRESHOLD` (default 5%) |
| Liquidation distance | `data/refresh_pipeline.py` | Passed to `alert_top_strategies()` |

---

## Future Enhancements

Potential additions:
- **Portfolio performance summary** (daily/weekly digest)
- **Price alert notifications** (token price movements)
- **Liquidation warnings** (positions approaching liquidation)
- **Auto-rebalance confirmations** (before executing)
- **Gas usage tracking** (transaction cost alerts)

---

## Related Documentation

- [Architecture Overview](Architecture.md)
- [Design Notes](design_notes.md)
- [Portfolio Reference](portfolio_reference.md)
- [Rebalancing Plan](../.claude/plans/replicated-mixing-wilkinson.md)
