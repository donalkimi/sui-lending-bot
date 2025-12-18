# Slack Workflows Setup Guide

## 📋 Complete Setup Instructions

### Step 1: Create Workflow in Slack

1. **Open Workflow Builder**
   - Click **Tools** (top right of Slack)
   - Select **Workflow Builder**
   - Click **Create** (or **New Workflow**)

2. **Configure Workflow Start**
   - Choose: **"Webhook"** (or "Starts from a webhook")
   - Name: `Sui Lending Bot Alerts`
   - Click **Next** or **Add Variables**

3. **Add Variables**
   Click "Add variable" for each of these:

   ```
   Variable Name       | Data Type
   --------------------|----------
   net_apr             | Text
   liquidation_distance| Text
   token1              | Text
   token2              | Text
   protocol_A          | Text
   protocol_B          | Text
   lend_amount         | Text
   borrow_amount_1     | Text
   lend_amount_2       | Text
   borrow_amount_2     | Text
   lend_rate_1A        | Text
   borrow_rate_2A      | Text
   lend_rate_2B        | Text
   borrow_rate_1B      | Text
   timestamp           | Text
   ```

4. **Add Step: Send Message**
   - Click **Add Step**
   - Choose **"Send a message"**
   - Select channel: `#sui_lending_bot` (or your channel)
   - Who will post: Choose a name/icon for your bot

5. **Format the Message**
   
   Copy and paste this template into the message box:

   ```
   🚀 *High APR Opportunity Found!*

   *Net APR:* {}net_apr%
   *Liquidation Distance:* {}liquidation_distance%

   *Token Pair:* {}token1 ↔ {}token2
   *Protocols:* {}protocol_A ↔ {}protocol_B

   *Strategy:*
   • Lend {}lend_amount {}token1 in {}protocol_A @ {}lend_rate_1A%
   • Borrow {}borrow_amount_1 {}token2 from {}protocol_A @ {}borrow_rate_2A%
   • Lend {}lend_amount_2 {}token2 in {}protocol_B @ {}lend_rate_2B%
   • Borrow {}borrow_amount_2 {}token1 from {}protocol_B @ {}borrow_rate_1B%

   _Detected at {}timestamp_
   ```

   **Tip**: Use `{}variable_name` syntax where `{}` are the literal characters followed by the variable name

6. **Publish Workflow**
   - Click **Publish** (top right)
   - **Copy the webhook URL** 
   - Format will be: `https://hooks.slack.com/workflows/...` or `https://hooks.slack.com/triggers/...`

### Step 2: Configure Bot

1. **Add webhook to config**
   
   Edit `config/settings.py`:
   ```python
   SLACK_WEBHOOK_URL = "https://hooks.slack.com/workflows/T.../your_webhook_url_here"
   ```

2. **That's it!** The bot now sends variables automatically

### Step 3: Test It

**Option 1: Quick Test**
```bash
cd sui-lending-bot-complete
python -c "
from alerts.slack_notifier import SlackNotifier

notifier = SlackNotifier()

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

notifier.alert_high_apr(test_strategy)
print('Check Slack!')
"
```

**Option 2: Test with curl**
```bash
curl -X POST YOUR_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{
    "net_apr": "15.50",
    "leverage": "1.09",
    "token1": "USDY",
    "token2": "DEEP",
    "protocol_A": "NAVI",
    "protocol_B": "SuiLend",
    "lend_amount": "1.09",
    "borrow_amount_1": "0.63",
    "lend_amount_2": "0.63",
    "borrow_amount_2": "0.09",
    "lend_rate_1A": "9.70",
    "borrow_rate_2A": "19.50",
    "lend_rate_2B": "31.00",
    "borrow_rate_1B": "5.90",
    "timestamp": "2024-12-17 10:30:00 UTC"
  }'
```

## 📝 Available Variables Reference

The bot automatically sends these variables:

### High APR Alert Variables:
| Variable | Description | Example |
|----------|-------------|---------|
| `net_apr` | Net annual percentage rate | "15.50" |
| `liquidation_distance` | Safety buffer from liquidation (%) | "30" |
| `token1` | Stablecoin being lent | "USDY" |
| `token2` | High-yield token | "DEEP" |
| `protocol_A` | First protocol | "NAVI" |
| `protocol_B` | Second protocol | "SuiLend" |
| `lend_amount` | Total token1 lent in A | "1.09" |
| `borrow_amount_1` | Total token2 borrowed from A | "0.63" |
| `lend_amount_2` | Total token2 lent in B | "0.63" |
| `borrow_amount_2` | Total token1 borrowed from B | "0.09" |
| `lend_rate_1A` | Token1 lending rate in A | "9.70" |
| `borrow_rate_2A` | Token2 borrow rate from A | "19.50" |
| `lend_rate_2B` | Token2 lending rate in B | "31.00" |
| `borrow_rate_1B` | Token1 borrow rate from B | "5.90" |
| `timestamp` | When detected | "2024-12-17 10:30:00 UTC" |

### Rebalance Alert Variables:
| Variable | Description | Example |
|----------|-------------|---------|
| `apr_improvement` | APR increase | "2.50" |
| `current_apr` | Current strategy APR | "13.00" |
| `new_apr` | New strategy APR | "15.50" |
| `current_token1` | Current stablecoin | "USDC" |
| `current_token2` | Current high-yield token | "WAL" |
| `current_protocol_A` | Current first protocol | "NAVI" |
| `current_protocol_B` | Current second protocol | "Scallop" |
| `new_token1` | Recommended stablecoin | "USDY" |
| `new_token2` | Recommended high-yield token | "DEEP" |
| `new_protocol_A` | Recommended first protocol | "NAVI" |
| `new_protocol_B` | Recommended second protocol | "SuiLend" |
| `liquidation_distance` | New liquidation distance (%) | "30" |
| `timestamp` | When detected | "2024-12-17 10:30:00 UTC" |

## 🎨 Message Formatting Tips

### Using Markdown in Slack:
- **Bold**: `*text*` → *text*
- _Italic_: `_text_` → _text_
- `Code`: `` `text` `` → `text`
- Bullet: `• text` → • text
- Emoji: `:rocket:` → 🚀

### Example Advanced Message:
```
:rocket: *High APR Alert!*

:chart_with_upwards_trend: *{}net_apr% APR* ({}leveragex leverage)

:coin: *Tokens:* {}token1 → {}token2
:building_construction: *Protocols:* {}protocol_A → {}protocol_B

:memo: *Position Breakdown:*
```
Lend:    {}lend_amount {}token1 @ {}lend_rate_1A%
Borrow:  {}borrow_amount_1 {}token2 @ {}borrow_rate_2A%
Lend:    {}lend_amount_2 {}token2 @ {}lend_rate_2B%
Borrow:  {}borrow_amount_2 {}token1 @ {}borrow_rate_1B%
```

:clock3: _{}timestamp_
```

## 🔧 Optional: Create Multiple Workflows

You can create different workflows for different alert types:

### Workflow 1: High APR Alerts
- Name: `High APR Alert`
- Trigger: When APR > 5%
- Use variables: `net_apr`, `leverage`, `token1`, `token2`, etc.

### Workflow 2: Rebalance Alerts
- Name: `Rebalance Alert`
- Trigger: When better opportunity found
- Use variables: `current_apr`, `new_apr`, `apr_improvement`, etc.

### Workflow 3: Error Alerts
- Name: `Bot Error`
- Variables: `error_message`, `timestamp`

Then in `config/settings.py`:
```python
SLACK_HIGH_APR_WEBHOOK = "https://hooks.slack.com/workflows/..."
SLACK_REBALANCE_WEBHOOK = "https://hooks.slack.com/workflows/..."
SLACK_ERROR_WEBHOOK = "https://hooks.slack.com/workflows/..."
```

## 🐛 Troubleshooting

### "Workflow test failed"
- Make sure all variables are defined in the workflow
- Variable names must match exactly (case-sensitive)
- Check that the webhook URL is correct

### "Variables not showing in message"
- Variables must use `{}variable_name` syntax (empty braces followed by variable name)
- Make sure you defined the variable in Step 3
- Variable names are case-sensitive and must match exactly

### "Message not appearing in channel"
- Check that the workflow is published (not draft)
- Verify the channel is correct
- Check that the bot has permission to post

### "Bot says webhook not configured"
- Check `config/settings.py` has the correct URL
- URL should start with `https://hooks.slack.com/workflows/` or `https://hooks.slack.com/triggers/`
- Remove the `YOUR_SLACK_WEBHOOK_URL_HERE` placeholder

## ✅ Quick Checklist

- [ ] Workflow created in Slack
- [ ] All 15 variables added
- [ ] Message formatted with {{variables}}
- [ ] Workflow published
- [ ] Webhook URL copied
- [ ] URL added to config/settings.py
- [ ] Test message sent successfully
- [ ] Message appears correctly formatted in Slack

## 🎉 You're Done!

Your bot will now send beautifully formatted alerts to Slack with all the strategy details!

To see it in action:
```bash
python main.py --once
```

If the bot finds a good opportunity, you'll get a Slack notification!
