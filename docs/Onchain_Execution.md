# Phase 2: Onchain Transaction Execution - Implementation Plan

## Context

This plan outlines the implementation of an **onchain transaction execution system** for Sui blockchain lending operations.

**Current State:**
- Read-only SDK integrations with lending protocols (Suilend, AlphaFi, Navi, Scallop, Bluefin)
- No onchain execution capability

**Goal:**
Build an execution engine that processes instructions from Sui-Yield-Bot to execute yield strategies onchain. The system should:
1. **Accept instruction specifications** - Bot provides token, amount, protocol, direction, tolerances, and any other required parameters
2. **Validate onchain conditions** - Check for discrepancies between bot expectations (prices, rates) and actual onchain state; abort if differences exceed tolerances
3. **Generate and execute transactions** - Convert specifications to actual blockchain transactions
4. **Monitor execution** - Track transaction status and on-chain state
5. **Handle failures gracefully** - Retry, rollback, or alert on errors

**Intended Outcome:**
A robust, safe execution engine that takes bot-generated instruction specifications and reliably executes them onchain with comprehensive validation, monitoring, error handling, and risk management.

---

## Sui-Yield-Bot Instruction Model

### Input Specification

The Sui-Yield-Bot generates instruction specifications for the execution engine. The bot can provide any parameters needed - the fields below are examples of what might be included:

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

**Note for Implementation Team:** If you need additional parameters from the bot (e.g., health factor thresholds, liquidation buffers, rebalance triggers, etc.), request them. The bot can generate any information the execution system requires.

### Example: Single Lend Operation

```python
# Bot generates instruction to lend 1000 USDC on Suilend
spec = {
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
}

# System generates transaction, validates, executes, monitors
result = execute_instruction(spec)
```

### Example: Multi-Leg Operation

```python
# Bot generates instruction to execute a 2-leg strategy
specs = [
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

# System generates transaction batch, validates all legs, executes in order
result = execute_instruction_batch(specs)
```

**Key Point:** The system does NOT decide what to execute. The bot specifies everything explicitly. The system's job is to safely execute those instructions.

---

## Required Capabilities

### Progressive Complexity

The execution system should be built progressively, starting simple and adding complexity:

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

---

## Safety Requirements

The execution system must validate conditions before executing transactions:

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

These principles should guide the implementation:

1. **Instruction-Driven**: Bot specifies ALL parameters explicitly. No automatic decision-making by the execution system.

2. **Works with Any Protocol**: The bot can send instructions for any protocol (Suilend, Navi, AlphaFi, Scallop, etc.) without the core system needing to change. Adding support for a new protocol shouldn't require rewriting existing code.

3. **Fail-Safe Design**: Multiple validation layers, pre-flight checks, simulation before real execution.

4. **Event Sourcing**: All transactions logged immutably for audit trail and debugging.

5. **Idempotent Operations**: Retrying failed operations is safe - system detects and handles duplicates.

6. **Observable**: Comprehensive logging, monitoring, and state tracking for debugging and auditing.

---

## Success Metrics

The execution system should achieve:

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

**Version:** 2.0
**Status:** Requirements Document
**Created:** 2026-02-17
**Updated:** 2026-02-17

**Changes from v1.0:**
- Refactored to focus on bot-specified instructions
- Removed prescriptive implementation details
- Changed from detailed architecture to requirements document
- Focus on WHAT needs to be built, not HOW to build it
ß
**Next Steps:**
1. Implementation team reviews requirements
2. Team designs architecture and approach
3. Team raises any questions about bot instruction format
4. Begin implementation with Phase 2A (single-leg operations)
