# Strategy Selection Logic

## How the Bot Chooses the "Best" Strategy

The bot uses a simple, clear ranking system:

### Primary Sort: Net APR (Descending)
**The strategy with the highest net APR wins.**

Example:
- Strategy A: USDY → DEEP = 15.50% APR
- Strategy B: USDC → suiUSDT = 12.29% APR
- Strategy C: USDC → WAL = 14.00% APR

**Winner: Strategy A** (15.50% is highest)

### Secondary Sort: Stablecoin-Only Preference (Tiebreaker)
**If two strategies have the SAME net APR, prefer stablecoin-only (lower risk).**

Example:
- Strategy A: USDY → DEEP = 15.50% APR (stablecoin + high-yield)
- Strategy B: USDC → suiUSDT = 15.50% APR (stablecoin-only)

**Winner: Strategy B** (same APR, but stablecoin-only = lower risk)

## Strategy Types

### Type 1: Stablecoin-Only
- Token 1: Stablecoin (USDC, suiUSDT, USDY, AUSD, FDUSD)
- Token 2: Stablecoin (USDC, suiUSDT, USDY, AUSD, FDUSD)
- Risk: Lower (no price exposure to volatile tokens)
- Typical APR: Lower (smaller spreads)

### Type 2: Stablecoin + High-Yield
- Token 1: Stablecoin (USDC, suiUSDT, USDY, AUSD, FDUSD)
- Token 2: High-yield token (DEEP, WAL, BLUE, SUI)
- Risk: Higher (but still market-neutral due to offsetting positions)
- Typical APR: Higher (larger spreads on high-yield tokens)

## What You'll See

When you run the bot:

```
🏆 BEST STRATEGY FOUND (Stablecoin + High-yield):
   Protocol A: NAVI
   Protocol B: SuiLend
   Token 1: USDY
   Token 2: DEEP
   Net APR: 15.50%
   Liquidation Distance: 30%
```

Or if a stablecoin-only strategy wins:

```
🏆 BEST STRATEGY FOUND (Stablecoin-only):
   Protocol A: NAVI
   Protocol B: Scallop
   Token 1: USDC
   Token 2: suiUSDT
   Net APR: 12.29%
   Liquidation Distance: 30%
```

## Why This Makes Sense

1. **APR is king** - You want maximum yield
2. **Stablecoins as tiebreaker** - If yields are equal, why take extra risk?
3. **No artificial constraints** - Bot evaluates ALL strategies fairly

## Real-World Scenarios

### Scenario 1: High-Yield Token Has Great Spread
- DEEP lending @ 31%, borrowing @ 19.5% = 11.5% spread
- Even with stablecoin rates, total APR = 15%+
- **Winner: Stablecoin + DEEP strategy**

### Scenario 2: Stablecoin Rates Are Exceptional
- Some stablecoin has 12% lending, 3% borrowing = 9% spread
- Recursive positions amplify this
- Total APR = 16%
- **Winner: Stablecoin-only strategy** (and lower risk!)

### Scenario 3: Tie Situation
- Strategy A: USDC → DEEP = 14.00% APR
- Strategy B: USDC → suiUSDT = 14.00% APR
- **Winner: Strategy B** (stablecoin-only, safer)

## Bottom Line

The bot doesn't care about token types. It cares about **net APR**.

- Best APR wins
- Ties go to lower risk (stablecoin-only)
- Simple, objective, optimal

No manual filtering, no artificial preferences - just pure math.
