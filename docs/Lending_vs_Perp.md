# Perp Lending Strategy

## Overview

Market-neutral strategy that earns yield from both lending markets and perpetual funding rates.

## Mechanics

### Strategy Components

**Position A: Spot Lending (Long)**
- Buy spot token (BTC, ETH, SOL, etc.)
- Lend to protocol (Suilend, Navi, Scallop, etc.)
- Earn: Lending APR

**Position B: Perpetual Short**
- Short perp on Bluefin (BTC-PERP, ETH-PERP, etc.)
- Post USDC collateral
- Earn: Funding rate (when positive = shorts receive)

**Net exposure:**
- Market neutral (long spot cancels short perp)
- Basis risk ignored (assume spot price = perp price)
- Single protocol risk (only lending protocol)

### Capital Allocation

For $1 deployed:
- $L goes to buying spot and lending
- $S goes to posting as perp collateral
- $L + $S = $1 (total deployment)

**For market neutral: Short size must equal spot size**
- Perp notional = $L (match spot position)
- Leverage = Perp notional / Collateral = $L / $S

### Liquidation Distance

**Key formula:** Nx leverage => liquidation at (1 + 1/N)× price change

**For shorts:**
- Liquidation when collateral = loss from price increase
- Loss = Position × Price_change%
- $S = $L × (1/N) where N = leverage
- Price increase to liquidation = 1/N = S/L

**Examples:**

| Split | L | S | Leverage | Liq Distance | Liq Price |
|-------|---|---|----------|--------------|-----------|
| 83.33/16.67 | $0.83 | $0.17 | 5x | 20% | 1.20× entry |
| 50/50 | $0.50 | $0.50 | 1x | 100% | 2.0× entry |
| 67/33 | $0.67 | $0.33 | 2x | 50% | 1.5× entry |
| 75/25 | $0.75 | $0.25 | 3x | 33% | 1.33× entry |
| 80/20 | $0.80 | $0.20 | 4x | 25% | 1.25× entry |

**Formula derivation:**

Given desired liquidation distance d:
- Leverage N = 1/d
- S/L = d
- L + S = 1
- L(1 + d) = 1
- **L = 1/(1 + d)**
- **S = d/(1 + d)**

**Example: 20% liquidation distance**
- L = 1/(1 + 0.2) = 1/1.2 = 0.8333 = 83.33%
- S = 0.2/(1 + 0.2) = 0.2/1.2 = 0.1667 = 16.67%
- Leverage = 0.8333/0.1667 = 5x
- Liquidation at 20% price increase

### Mapping to Existing Framework

The system uses position multipliers (L_A, B_A, L_B, B_B) to represent all strategies.

**For perp lending:**
```python
L_A = 1/(1 + liquidation_distance)  # Spot lending
B_A = 0.0                            # No borrowing
L_B = 0.0                            # No second lending
B_B = liquidation_distance/(1 + liquidation_distance)  # Perp short
```

**Example (20% liquidation distance):**
- L_A = 1/(1 + 0.2) = 0.8333 (83.33%)
- B_A = 0.0
- L_B = 0.0
- B_B = 0.2/(1 + 0.2) = 0.1667 (16.67%)

**Example (50/50 split, 100% liq distance):**
- L_A = 1/(1 + 1.0) = 0.5
- B_A = 0.0
- L_B = 0.0
- B_B = 1.0/(1 + 1.0) = 0.5

**Rate variables:**
- r_1A = Lending APR for spot token on Protocol A
- r_2A = 0 (no borrowing)
- r_2B = 0 (no lending on perp protocol)
- r_3B = Perp funding rate (annualized, from Bluefin)

**Net APR formula:**
```python
gross_earnings = L_A × r_1A + B_B × r_3B
upfront_fees = B_B × (2 × BLUEFIN_TAKER_FEE)  # Entry + exit
holding_period_years = 1.0  # Assume 1 year for APR
net_apr = gross_earnings - (upfront_fees / holding_period_years)
```

## Liquidation Formulas

### Short Perpetual Liquidation

**Setup:**
- Collateral: $C (USDC posted)
- Position: $P (notional value shorted)
- Entry price: P₀
- Current price: P
- Leverage: N = P/C

**Liquidation condition:**
Loss from price increase = Collateral

**Formula:**
```
P - P₀ = C × P/P₀  (loss in dollar terms)
P × P = C × P₀
P/P₀ = C/P = 1/N
P_liq = P₀ × (1 + 1/N)
```

**Liquidation distance:**
```
distance = (P_liq - P₀)/P₀ = 1/N = C/P
```

**For long perpetuals** (formula is symmetric):
```
P_liq = P₀ × (1 - 1/N)
distance = (P₀ - P_liq)/P₀ = 1/N
```

### Spot Lending Liquidation

**Key difference:** This strategy has NO liquidation risk on the spot side because:
1. We're not borrowing against the spot tokens
2. Spot tokens are collateral, not borrowed assets
3. Lending protocols don't liquidate lenders

**Effective liquidation distance:** ∞ (infinite) on lending side

## Fee Structure

### Perpetual Fees (Bluefin)

**Maker fee:** 0.01% (1 bps) - when you provide liquidity
**Taker fee:** 0.035% (3.5 bps) - when you take liquidity

**Conservative assumption:** Pay taker fee on both entry and exit
- Entry: 0.035% × position_size
- Exit: 0.035% × position_size
- **Total upfront:** 0.07% × position_size

**Stored as:**
```python
BLUEFIN_MAKER_FEE = 0.0001   # 0.01%
BLUEFIN_TAKER_FEE = 0.00035  # 0.035%
```

**Amortized over holding period:**
```python
annual_fee_drag = (2 × BLUEFIN_TAKER_FEE) / holding_period_years
```

### Lending Protocol Fees

Most lending protocols have zero entry/exit fees. Borrow fees are captured in the borrow_total_apr.

## Current Simplifications

**To be addressed later:**

1. **Basis risk:** Assume spot price = perp price (ignore cash-carry arbitrage)
2. **Maker/taker optimization:** Assume worst case (taker fees)
3. **Funding rate volatility:** Use current rate, no forecasting
4. **Rebalancing costs:** Ignore drift between spot and perp sizes
5. **Oracle risk:** Assume accurate price feeds

## Token Mappings

### Bluefin Perpetual Markets

Mapping is explicitly controlled in `config/settings.py` via `BLUEFIN_TO_LENDINGS` dictionary.

**Example structure:**
```python
BLUEFIN_TO_LENDINGS = {
    '0xBTC-USDC-PERP_bluefin': [
        '0xaafb...::btc::BTC',      # BTC
        '0x876a...::xbtc::XBTC',    # xBTC
        '0x41f9...::wbtc::WBTC',    # wBTC
        # ... other BTC-like tokens
    ],
    '0xETH-USDC-PERP_bluefin': [
        '0xaf8c...::coin::COIN',    # ETH
        '0xd0e8...::eth::ETH',      # wETH
        # ... other ETH-like tokens
    ],
    # ... other perp markets
}
```

**Generation:**
1. Query `token_registry` table
2. Filter to tokens with `pyth_id` OR `coingecko_id` (not neither)
3. Group by base asset (BTC, ETH, SOL, etc.)
4. Map to corresponding perp markets

**Strategy generation:** For each perp market, generate strategies for all mapped spot tokens on all lending protocols.

## Risk Analysis

### Risks Present

1. **Lending protocol risk:** Smart contract risk on lending side
2. **Funding rate reversal:** If funding goes negative, strategy loses
3. **Bluefin protocol risk:** Smart contract/liquidation engine risk
4. **Basis risk:** Spot and perp prices can diverge
5. **Liquidation risk:** If leverage too high, short gets liquidated

### Risks Absent (vs Recursive Lending)

1. **NO multi-protocol cascading:** Only 1 lending protocol
2. **NO double liquidation:** Spot side cannot be liquidated
3. **NO loop complexity:** Only 2 legs (lend + short)
4. **NO borrow rate spikes:** Not borrowing from lending protocols

### Risk Mitigation

- Start with conservative liquidation distance (100% = 50/50 split)
- Monitor funding rates hourly (already happening)
- Alert if funding goes negative (to be implemented)
- Rebalance when spot/perp ratio drifts >5%
