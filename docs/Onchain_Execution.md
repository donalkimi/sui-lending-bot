# Phase 2: Onchain Transaction Execution - Backend API Specification

## Context

This document specifies the **Backend API** that Sui-Yield-Bot will use to execute yield strategies onchain.

**Architecture:**
```
Sui-Yield-Bot → Backend API → Blockchain
```

**Current State:**
- Sui-Yield-Bot generates signals and analyzes opportunities (Phase 1)
- No execution capability

**Goal:**
The implementation team will build a Backend API that:
1. **Receives instructions** from Sui-Yield-Bot via API calls
2. **Validates onchain conditions** - Checks if prices/rates match bot expectations within tolerances
3. **Executes transactions** - Handles all blockchain interaction details
4. **Returns results** - Confirms execution or explains why it failed

**Intended Outcome:**
Sui-Yield-Bot can execute strategies by making simple API calls, without needing to know blockchain transaction details.

---

## API Request Format

### What the Bot Sends

The bot makes HTTP POST requests with instruction specifications. The bot can include any parameters needed - fields below are examples:

```python
# Example instruction specification (bot can provide additional fields as needed)
ExecutionSpec = {
    # Core Transaction Parameters
    "wallet_address": "0x...",           # Wallet to execute from
    "protocol": "suilend",               # Target protocol
    "action": "lend",                    # "lend", "borrow", "withdraw", "repay"
    "token_name": "USDC",                # Human-readable token name
    "token_contract": "0x...",           # Normalized contract address
    "amount": 1000.0,                    # Token amount to transact

    # Market Context (for validation)
    "expected_price": 1.0001,            # Expected token price in USD
    "expected_rate": 0.031,              # Expected APR (3.1%)
    "price_tolerance": 0.005,            # Max price deviation (0.5%)
    "rate_tolerance": 0.03,              # Max rate deviation (3%)

    # Execution Options
    "max_gas": 100.0,                    # Max gas in MIST
    "timeout_seconds": 60,               # Transaction timeout
    "execution_mode": "sequential"       # "sequential" or "parallel" (multi-tx)

    # ... bot can include any additional parameters the execution engine needs
}
```

**Note for Implementation Team:** If you need additional parameters from the bot (e.g., health factor thresholds, liquidation buffers, rebalance triggers, etc.), request them. The bot can provide any information needed.

### Example: Single Lend Operation

```python
# Bot makes API request to lend 1000 USDC on Suilend
import requests

response = requests.post("http://api-url/execute", json={
    "wallet_address": "0xabc123...",
    "protocol": "suilend",
    "action": "lend",
    "token_name": "USDC",
    "token_contract": "0x5d4b302506645c37ff133b98c4b50a5ae14841659738d6d733d59d0d217a93bf::coin::COIN",
    "amount": 1000.0,
    "expected_price": 1.0001,
    "expected_rate": 0.031,  # 3.1%
    "price_tolerance": 0.005,
    "rate_tolerance": 0.03
})

result = response.json()
# result contains execution status, transaction hash, or error details
```

### Example: Multi-Leg Operation

```python
# Bot makes API request to execute 2-leg strategy
response = requests.post("http://api-url/execute-batch", json={
    "operations": [
        {
            "action": "lend",
            "protocol": "suilend",
            "token_name": "USDC",
            "token_contract": "0x...",
            "amount": 10000.0,
            "expected_rate": 0.03,
            # ... other params
        },
        {
            "action": "borrow",
            "protocol": "suilend",
            "token_name": "SUI",
            "token_contract": "0x2::sui::SUI",
            "amount": 2500.0,
            "expected_rate": 0.08,
            # ... other params
        }
    ]
})

result = response.json()
# result contains execution status for all operations
```

---

## API Response Format

### What the Bot Receives Back

The API should return clear success/failure responses:

**Success Response:**
```json
{
    "success": true,
    "transaction_hash": "0xabc123...",
    "actual_price": 1.00009,
    "actual_rate": 0.0309,
    "gas_used": 0.045,
    "timestamp": 1707332400
}
```

**Failure Response:**
```json
{
    "success": false,
    "error_code": "RATE_DRIFT",
    "error_message": "Current rate 0.025 outside tolerance (expected 0.031 ± 3%)",
    "current_price": 1.00012,
    "current_rate": 0.025
}
```

**Multi-Leg Response:**
```json
{
    "success": true,
    "operations": [
        {"action": "lend", "status": "success", "transaction_hash": "0x123..."},
        {"action": "borrow", "status": "success", "transaction_hash": "0x456..."}
    ],
    "total_gas_used": 0.089
}
```

**Key Point:** The bot specifies what to execute, the API handles all blockchain details and returns results.

---

## API Capabilities

### Progressive Implementation

The Backend API should be built progressively, starting simple and adding complexity:

**Phase 2A: Single-Leg Operations (MVP)**
- Lend single token to single protocol
- Withdraw from single protocol
- Example: Lend 1000 USDC to Suilend

**Phase 2B: Two-Leg Same Protocol**
- Lend + Borrow on same protocol
- Health factor monitoring
- Example: Lend USDC, borrow SUI (both Suilend)

**Phase 2C: Multi-Leg Cross-Protocol**
- Operations spanning multiple protocols
- Complex transaction sequencing
- Example: Lend USDC @ Protocol A, borrow WAL @ Protocol A, lend WAL @ Protocol B

**Phase 2C-i: Flash Loan Investigation**
- Investigate using flash loans to execute leveraged/loop strategies in single transaction
- Flash loan enables borrowing without upfront capital, repaying within same transaction

**Phase 2C-ii: Capital-Backed Loop Execution**
- Alternative to flash loans: Use available capital to enable one-step loop execution
- Bot supplies extra capital upfront to complete loop, returns capital at end of transaction
- Eliminates flash loan complexity and fees

**Phase 2D: Swap Integration**
- DEX swap operations
- Example: Swap 1000 WAL to DEEP on Cetus

**Phase 2E: Perpetual Futures**
- Perp position operations
- Example: Short 10x SUI-PERP on Bluefin

**Phase 2F: Spot vs Perp Spread Execution**
- Simultaneous spot and perp execution to capture basis/spread
- Opposite positions on spot DEX and perpetual futures
- Example: Sell 100 BTC on Cetus spot at $68,000 + Long 100 BTC-USDC-PERP on Bluefin at $68,125 (capture $125 spread)
- Execution: Sequential with price tolerance checks (atomic execution ideal but not required)
- Bot can specify execution order and acceptable price ranges to manage legging risk

---

## Safety Requirements

The Backend API must validate conditions before executing transactions:

### Pre-Execution Validation

**Rate Validation**
- Current protocol rates within bot-specified tolerance
- Detect suspicious rate spikes (oracle manipulation)

**Price Validation**
- Current token prices within bot-specified tolerance
- Oracle prices consistent across sources
- No flash crash or anomaly detection

**Liquidity Validation**
- Protocol has sufficient liquidity for requested amount
- Transaction won't significantly move market
- Includes safety buffer

**Collateral Validation** (for borrow operations)
- Projected health factor remains safe (e.g., > 1.5)
- Liquidation distance maintains buffer (e.g., > 20%)
- Collateral ratios within protocol limits

**Gas Validation**
- Gas prices within acceptable range
- Wallet has sufficient balance for gas + transaction

**Position Limits**
- Respects protocol position size limits
- Respects configured wallet exposure limits

### Post-Execution Monitoring

**Health Monitoring**
- Continuous health factor tracking (for borrow positions)
- Alert on warning thresholds (< 2.0) and critical thresholds (< 1.5)
- Liquidation distance tracking

**State Reconciliation**
- Compare actual onchain state with expected state
- Flag discrepancies > 1% for investigation
- Alert on drift > 5%

**Execution Tracking**
- Log all transactions immutably
- Track transaction status (pending, confirmed, failed)
- Monitor for unexpected liquidations

### Error Handling

**Retry Strategy**
- Retry transient errors (RPC timeout, nonce conflicts)
- No retry for permanent errors (insufficient balance, invalid transaction)
- Circuit breaker after N consecutive failures

**Rollback Capability**
- For partial multi-leg executions, ability to rollback/compensate
- Calculate rollback cost vs leaving partial position
- Alert implementation team for complex failures

---

## Key Architectural Principles

These principles should guide the API implementation:

1. **Instruction-Driven**: Bot specifies ALL parameters explicitly via API requests. No automatic decision-making by the API.

2. **Protocol Support**: The API should support multiple protocols (Suilend, Navi, AlphaFi, Scallop, etc.). The bot just specifies which protocol in the request.

3. **Fail-Safe Design**: API validates all conditions before executing. Returns clear error if validation fails.

4. **Transaction Logging**: All API requests and blockchain transactions logged for audit trail and debugging.

5. **Idempotent**: Retrying the same API request is safe - API detects duplicates.

6. **Clear Responses**: API always returns success/failure status with details. Bot can log and alert based on response.

---

## Success Metrics

The Backend API should achieve:

**Reliability**
- Zero critical safety violations

**Safety**
- All pre-execution validations pass before committing capital
- No capital loss due to execution bugs

**Observability**
- All transactions logged with full context
- State reconciliation runs continuously
- Alerts sent on anomalies or threshold breaches

---

## Document Status

**Version:** 3.0
**Status:** API Specification
**Created:** 2026-02-17
**Updated:** 2026-02-17

**Changes from v2.0:**
- Refactored to reflect Backend API architecture
- Bot interacts via HTTP API, not direct blockchain integration
- Clear separation: Bot → API → Blockchain
- Focused on API request/response format
- Implementation team builds the API backend

**Next Steps:**
1. Implementation team reviews API specification
2. Team provides feedback on request/response format
3. Team shares API endpoint URLs and authentication method
4. Bot can start making API calls once endpoints are ready
