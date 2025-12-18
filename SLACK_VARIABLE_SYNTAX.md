# Slack Workflow Variable Syntax - Quick Reference

## ✅ CORRECT Syntax

In Slack Workflows, variables use this syntax:
```
{}variable_name
```

That's literally:
- Two curly braces: `{}`
- Immediately followed by the variable name (no space)

## Examples:

| Variable | Correct Syntax | Result |
|----------|---------------|---------|
| net_apr | `{}net_apr` | Shows the APR value |
| leverage | `{}leverage` | Shows the leverage value |
| token1 | `{}token1` | Shows the token name |

## Complete Message Example:

```
🚀 *High APR Alert!*

Net APR: {}net_apr%
Leverage: {}leveragex

Tokens: {}token1 and {}token2
Protocols: {}protocol_A and {}protocol_B
```

## ❌ WRONG Syntax

These will NOT work:

| Wrong | Why |
|-------|-----|
| `{net_apr}` | Single braces with variable inside |
| `{{net_apr}}` | Double braces wrapping variable |
| `{ net_apr }` | Spaces inside braces |
| `{} net_apr` | Space between {} and variable name |

## Copy-Paste Ready Template

```
🚀 *High APR Opportunity Found!*

*Net APR:* {}net_apr%
*Leverage:* {}leveragex

*Token Pair:* {}token1 ↔ {}token2
*Protocols:* {}protocol_A ↔ {}protocol_B

*Strategy:*
• Lend {}lend_amount {}token1 in {}protocol_A @ {}lend_rate_1A%
• Borrow {}borrow_amount_1 {}token2 from {}protocol_A @ {}borrow_rate_2A%
• Lend {}lend_amount_2 {}token2 in {}protocol_B @ {}lend_rate_2B%
• Borrow {}borrow_amount_2 {}token1 from {}protocol_B @ {}borrow_rate_1B%

_Detected at {}timestamp_
```

Just copy the above and paste it into your Slack Workflow message editor!
