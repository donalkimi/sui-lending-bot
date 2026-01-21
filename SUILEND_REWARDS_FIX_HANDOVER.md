# Suilend Rewards Fix - Handover Document

## Date
2026-01-21

## Problems Discovered

### 1. Suilend Reward APRs Showing as NaN (FIXED)
**Issue:** Tokens with rewards (AUSD, WAL, LBTC) showed NULL/NaN in database for both base and total APRs.

**Root Cause:** Missing `decimals` field in fallback coin metadata caused SDK's `formatRewards()` to return NaN.

**Fix Applied:**
- Added `decimals: 9` to fallback metadata in `suilend_reader-sdk.mjs` (line 111)
- Changed reward calculation to use `getDedupedAprRewards()` + manual summation instead of broken `getTotalAprPercent()`

**Result:** AUSD rewards now show correctly (3.84% sSUI rewards).

---

### 2. DEEP Reward APR Off by 1000x (CURRENT ISSUE)

**Symptom:**
- DEEP token lends with rewards in both **sSUI** (7.59%) and **DEEP** (18.47%)
- sSUI rewards calculate correctly: 7.59% ✓
- DEEP rewards calculate incorrectly: **0.0185%** instead of **18.47%** ✗
- Error is exactly **1000x** (10^3)

**Root Cause Identified:**
- DEEP token has **6 decimals** (verified on blockchain explorer)
- Our fallback code defaults ALL tokens to **9 decimals**
- SDK's `formatRewards()` uses decimals to calculate APR: `rewardAmount / 10^decimals`
- Wrong decimals causes: `rewardAmount / 10^9` instead of `rewardAmount / 10^6`
- Ratio: 10^9 / 10^6 = **1000x difference**

**Evidence:**
```
Debug output shows:
- DEEP reward token: mintDecimals: 9 (WRONG - should be 6)
- coinMetadataMap decimals: 9 (WRONG - our hardcoded fallback)
- aprPercent: 0.0184463303246485 (0.0185% - OFF BY 1000x)

Actual from blockchain:
- DEEP decimals: 6 ✓
- Expected reward APR: 18.47% ✓
```

**Why sSUI Works But DEEP Doesn't:**
- SPRING_SUI (sSUI) actually HAS 9 decimals → hardcoded fallback is correct ✓
- DEEP actually HAS 6 decimals → hardcoded fallback is wrong ✗

---

## Proposed Solution: Token Registry Enhancement

### Problem with Current Approach
Currently, when metadata fetch fails, we fall back to hardcoding `decimals: 9` for all tokens. This breaks tokens with different decimal precision (like DEEP with 6 decimals).

### Better Solution: Store Metadata in Database

**Add columns to `token_registry` table:**
1. **`decimals`** (INTEGER) - Token decimal precision (6 for DEEP, 9 for SUI)
2. **`default_price`** (FLOAT) - Fallback price when live price unavailable

**Benefits:**
- ✅ Fetch coin metadata from RPC **once** when token first added
- ✅ Cache decimals in database for all future runs
- ✅ No repeated RPC calls (performance + rate limit friendly)
- ✅ Single source of truth for token metadata
- ✅ Fallback price for when live prices fail

### Implementation Plan

#### Phase 1: Database Schema
**File:** Migration script or manual ALTER TABLE

```sql
ALTER TABLE token_registry
ADD COLUMN decimals INTEGER DEFAULT 9,
ADD COLUMN default_price FLOAT DEFAULT NULL;
```

#### Phase 2: Metadata Fetching
**File:** `data/rate_tracker.py` (or new `data/token_metadata_fetcher.py`)

When upserting tokens to registry:
1. Check if token already has decimals stored
2. If missing, fetch from Sui RPC: `suiClient.getCoinMetadata(coinType)`
3. Store `decimals` and current price as `default_price`
4. Update existing tokens with NULL decimals

**Python Example:**
```python
from pysui import SuiClient

def fetch_and_store_token_metadata(token_contract):
    """Fetch coin metadata from RPC and store in token_registry"""
    client = SuiClient(rpc_url)
    metadata = client.get_coin_metadata(token_contract)

    return {
        'decimals': metadata.decimals,
        'symbol': metadata.symbol,
        'name': metadata.name,
        'default_price': get_current_price(token_contract)  # from existing price source
    }
```

#### Phase 3: Update Metadata Helper
**File:** `data/suilend/get_token_metadata.py`

Update to return decimals from `token_registry`:
```python
def get_token_metadata_from_db(coin_types: List[str]) -> Dict:
    """Query token_registry for metadata including decimals"""
    # SELECT symbol, name, decimals, default_price
    # FROM token_registry
    # WHERE token_contract IN (...)
```

**Also fix path issue:** The helper is being called with wrong path (`C:\\C:\\Dev\\...`)
- Issue in `suilend_reader-sdk.mjs` line 86-90
- Fix path construction to avoid double prefix

#### Phase 4: Backfill Existing Tokens
**One-time script** to populate decimals for all existing tokens in registry:

```python
# Fetch metadata for all tokens missing decimals
tokens_without_decimals = db.query("SELECT token_contract FROM token_registry WHERE decimals IS NULL")
for token in tokens_without_decimals:
    metadata = fetch_coin_metadata_from_rpc(token.token_contract)
    db.execute("UPDATE token_registry SET decimals = ?, default_price = ? WHERE token_contract = ?",
               metadata.decimals, metadata.price, token.token_contract)
```

---

## Files to Modify

### 1. Database Schema
- **Action:** Add `decimals` and `default_price` columns to `token_registry`

### 2. `data/rate_tracker.py`
- **Location:** `upsert_token_registry()` method
- **Change:** Fetch and store `decimals` + `default_price` for new tokens

### 3. `data/suilend/get_token_metadata.py`
- **Change 1:** Return `decimals` from database query
- **Change 2:** If token not in DB, fetch from RPC and cache it

### 4. `data/suilend/suilend_reader-sdk.mjs`
- **Change:** Fix path issue calling Python helper (line 86-90)
- **Keep:** Current fallback logic with `decimals: 9` (for emergency cases)
- **Revert:** Remove DEBUG mode and temporary debug logging

### 5. `data/protocol_merger.py` (Optional)
- **Change:** Use `default_price` as fallback when live price is NULL

---

## Verification Steps

After implementing fixes:

1. **Verify DEEP decimals in database:**
   ```sql
   SELECT symbol, token_contract, decimals, default_price
   FROM token_registry
   WHERE symbol = 'DEEP';
   ```
   Expected: `decimals = 6`

2. **Run Suilend reader:**
   ```bash
   cd data/suilend && node suilend_reader-sdk.mjs | grep -A 20 '"token_symbol": "DEEP"'
   ```
   Expected: `"lend_apr_reward": "25.606"` (approximately 18% DEEP + 7.6% sSUI)

3. **Check database rates:**
   ```sql
   SELECT token, lend_base_apr, lend_reward_apr, lend_total_apr
   FROM rates_snapshot
   WHERE protocol = 'Suilend' AND token = 'DEEP'
   AND timestamp = (SELECT MAX(timestamp) FROM rates_snapshot WHERE protocol = 'Suilend')
   ```
   Expected: All values valid numbers, reward_apr ≈ 25.6%

4. **Verify math:** `lend_total_apr = lend_base_apr + lend_reward_apr`

---

## Open Questions

1. **Python helper path fix:** Should we fix the `C:\\C:\\` double path issue, or just make the JavaScript fetch metadata directly?
   - **Recommendation:** Fix both - use Python helper as primary, JS SuiClient as fallback

2. **Default price update frequency:** How often should we update `default_price`?
   - **Options:** Daily, weekly, hourly, or only on first insert
   - **Recommendation:** Update during every refresh, but use as fallback only when live price unavailable

3. **Backfill strategy:** Should we backfill all tokens immediately or lazily (on-demand)?
   - **Recommendation:** Backfill all existing tokens immediately via one-time script

---

## Success Criteria

✅ DEEP rewards show correct APR (~18.47% for DEEP token rewards)
✅ All Suilend tokens with rewards calculate correctly
✅ Decimals cached in database, no repeated RPC calls
✅ Fallback price available for all tokens
✅ No NaN or NULL values in rates_snapshot for Suilend

---

## Related Files

### Previously Fixed
- ✅ `data/rate_tracker.py` - Fixed Scallop double-counting (lines 148-171)
- ✅ `data/scallop_shared/scallop_reader-sdk.mjs` - Filter deprecated assets
- ✅ `data/suilend/suilend_reader-sdk.mjs` - Added decimals fallback, fixed NaN rewards

### To Be Modified
- ⏳ Database schema (token_registry table)
- ⏳ `data/rate_tracker.py` - Metadata fetching in upsert
- ⏳ `data/suilend/get_token_metadata.py` - Return decimals from DB
- ⏳ `data/suilend/suilend_reader-sdk.mjs` - Fix Python helper path

---

## Notes

- **Current state:** Suilend rewards work for tokens with 9 decimals (AUSD, SUI, sSUI)
- **Broken:** Tokens with different decimals (DEEP=6, possibly USDC=6, USDT=6)
- **Impact:** Any token used as reward with ≠9 decimals will have wrong APR
- **Priority:** HIGH - affects strategy calculations and user-facing APR displays