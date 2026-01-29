# Pebble Protocol Market Segregation - Design Analysis

## Executive Summary

**The Problem:** Pebble has 3 separate lending pools (MainMarket, XSuiMarket, AltCoinMarket). You can ONLY borrow against collateral posted in the SAME pool. Currently, the system ignores which market positions use, treating Pebble as a single unified protocol. This allows the system to suggest invalid cross-market borrowing strategies.

**Current Flaw:** `pebble_reader.py` fetches all 3 markets separately, then deduplicates by picking the "best rate" (highest supply APR, lowest borrow APR, highest LTV). Market information is permanently discarded after deduplication (lines 368-371).

**Impact:** Position calculator can suggest strategies like "lend USDC in MainMarket, borrow DEEP from ALT_MARKET" which are impossible to execute on-chain.

---

## Current Implementation Analysis

### Data Flow
```
Fetch → [MainMarket, XSuiMarket, AltCoinMarket]
  ↓
Deduplication (_dedupe_best_rates) → Keep highest supply APR, lowest borrow APR per token
  ↓
Market info DISCARDED
  ↓
Protocol merger → "Pebble" column only
  ↓
Positions → protocol_A="Pebble", protocol_B="Pebble" (no market info)
```

### Key Files
- [pebble_reader.py](c:\Dev\sui-lending-bot\data\pebble\pebble_reader.py):25 - Defines MARKET_TYPES
- [pebble_reader.py](c:\Dev\sui-lending-bot\data\pebble\pebble_reader.py):368-371 - Deduplication logic (loses market info)
- [protocol_merger.py](c:\Dev\sui-lending-bot\data\protocol_merger.py):169 - Protocol list
- [protocol_merger.py](c:\Dev\sui-lending-bot\data\protocol_merger.py):319-327 - Scallop filtering precedent
- [schema.sql](c:\Dev\sui-lending-bot\data\schema.sql):46-47 - UNUSED `market` and `side` columns (hint at planned support)

### Scallop Precedent
Scallop splits into `ScallopLend` and `ScallopBorrow` as separate "protocol" names, but filtering logic treats them as ONE protocol (protocol_merger.py:324). This shows the system already supports protocol splitting.

---

## Approach 1: Split Protocol Names (Following Scallop Pattern)

### Overview
Create `PebbleMain`, `PebbleXSui`, `PebbleAlt` as separate "protocols" in the system.

### Implementation Details

**Step 1:** Modify [pebble_reader.py](c:\Dev\sui-lending-bot\data\pebble\pebble_reader.py)
- Remove `_dedupe_best_rates()` call (line 369-371)
- Instead of returning single DataFrames, return 3 separate sets
- Add market type to each record before returning

**Step 2:** Modify [protocol_merger.py](c:\Dev\sui-lending-bot\data\protocol_merger.py)
```python
# Line 169 - Update protocol list
protocols = ["Navi", "AlphaFi", "Suilend", "ScallopLend", "ScallopBorrow",
             "PebbleMain", "PebbleXSui", "PebbleAlt"]

# Lines 98-102 - Add instantiation logic (similar to existing Pebble)
elif protocol_name == "PebbleMain":
    config = PebbleReaderConfig(...)
    reader = PebbleMainReader(config)
    return reader.get_all_data()
# ... repeat for XSui and Alt

# Lines 319-327 - Add filtering logic (similar to Scallop)
has_pebble = (pd.notna(row.get('PebbleMain')) or
              pd.notna(row.get('PebbleXSui')) or
              pd.notna(row.get('PebbleAlt')))
```

**Step 3:** Create reader subclasses
```python
# pebble_main_reader.py
class PebbleMainReader(PebbleReader):
    def get_all_data(self):
        lend, borrow, coll = super().get_all_data()
        # Filter to MainMarket only
        return lend, borrow, coll

# Repeat for XSui and Alt
```

### Pros
- **Fast implementation** - 2-3 hours, follows existing pattern
- **No database changes** - works with current schema
- **Backward compatible** - existing queries work immediately
- **Zero migration risk** - no data loss possible
- **Proven pattern** - Scallop already works this way
- **Rate queries work** - protocol is part of (timestamp, protocol, token_contract) key

### Cons
- **Protocol count inflation** - Pebble counted as 3 protocols in some contexts
- **"Protocol" misnomer** - mixing protocol and market concepts
- **UI confusion** - users see "PebbleMain to PebbleXSui" instead of "Pebble (MainMarket → XSuiMarket)"
- **Historical data ambiguity** - old "Pebble" positions lose market context
- **Harder to filter** - need special logic to treat Pebble* as one protocol

### Database Impact
- No schema changes
- Existing positions with protocol="Pebble" need clarification (migration script to mark as deprecated or guess market)

### Files to Modify
1. [pebble_reader.py](c:\Dev\sui-lending-bot\data\pebble\pebble_reader.py) - Remove deduplication, create 3 subclasses
2. [protocol_merger.py](c:\Dev\sui-lending-bot\data\protocol_merger.py) - Add 3 protocols, add filtering logic
3. [rate_tracker.py](c:\Dev\sui-lending-bot\data\rate_tracker.py) - No changes (protocol is just a string)

### Verification
1. Run rate tracker and verify 3 Pebble columns appear in merged DataFrame
2. Create test position with protocol_A="PebbleMain", protocol_B="PebbleXSui"
3. Verify rate queries return correct market-specific rates
4. Verify filtering logic counts Pebble as 1 protocol (protocol_merger.py:327)

### Recommendation
**Best for: Quick fix to prevent invalid positions immediately**

---

## Approach 2: Use Market Column (Cleanest Architecture)

### Overview
Populate the UNUSED `market` column in rates_snapshot and extend the primary key to include market dimension.

### Implementation Details

**Step 1:** Database schema migration
```sql
-- Backup rates_snapshot
CREATE TABLE rates_snapshot_backup AS SELECT * FROM rates_snapshot;

-- Drop and recreate with new primary key
DROP TABLE rates_snapshot;

CREATE TABLE rates_snapshot (
    timestamp TEXT NOT NULL,
    protocol VARCHAR(50) NOT NULL,
    market VARCHAR(50) NOT NULL DEFAULT 'default',  -- NEW
    token VARCHAR(50) NOT NULL,
    token_contract TEXT NOT NULL,
    -- ... other columns ...
    PRIMARY KEY (timestamp, protocol, market, token_contract)  -- CHANGED
);

-- Add market columns to positions
ALTER TABLE positions ADD COLUMN protocol_A_market VARCHAR(50) DEFAULT 'default';
ALTER TABLE positions ADD COLUMN protocol_B_market VARCHAR(50) DEFAULT 'default';

-- Add market columns to position_rebalances
ALTER TABLE position_rebalances
    ADD COLUMN opening_protocol_A_market VARCHAR(50) DEFAULT 'default',
    ADD COLUMN opening_protocol_B_market VARCHAR(50) DEFAULT 'default',
    ADD COLUMN closing_protocol_A_market VARCHAR(50) DEFAULT 'default',
    ADD COLUMN closing_protocol_B_market VARCHAR(50) DEFAULT 'default';
```

**Step 2:** Modify [pebble_reader.py](c:\Dev\sui-lending-bot\data\pebble\pebble_reader.py)
- Keep market type attached to each record
- Do NOT deduplicate (remove lines 368-371)
- Return DataFrames with market info preserved

**Step 3:** Modify [protocol_merger.py](c:\Dev\sui-lending-bot\data\protocol_merger.py)
- Pass market through to merged DataFrames
- Store as (protocol, market) tuple or composite column name

**Step 4:** Update all rate queries in [position_service.py](c:\Dev\sui-lending-bot\analysis\position_service.py)
```python
# Line 748 - Update _query_rates_at_timestamp
WHERE timestamp = ?
  AND protocol = ?
  AND market = ?  -- NEW
  AND token_contract = ?
```

**Step 5:** Modify [rate_analyzer.py](c:\Dev\sui-lending-bot\analysis\rate_analyzer.py)
- Add market parameter to get_rate() method
- Update all call sites to pass market

### Pros
- **Semantically correct** - market is first-class concept
- **Clean data model** - proper separation of protocol vs market
- **Single "Pebble" protocol** - counts as 1 protocol in filtering
- **Explicit tracking** - market always known in database
- **Future-proof** - any protocol can have markets
- **Uses designed column** - `market` column was clearly planned for this

### Cons
- **Breaking change** - requires PRIMARY KEY modification
- **High implementation cost** - many files to update
- **Query changes everywhere** - all rate queries need market parameter
- **Migration complexity** - historical data needs market backfill (impossible to determine accurately)
- **Risk of data loss** - table rebuild required
- **Backward compatibility** - old positions incompatible without careful migration

### Database Impact
- PRIMARY KEY change: (timestamp, protocol, token_contract) → (timestamp, protocol, market, token_contract)
- Add 4-6 new VARCHAR columns to positions and rebalances tables
- Requires full table rebuild (can't ALTER PRIMARY KEY)
- Existing positions need market="default" for historical data

### Files to Modify
1. [schema.sql](c:\Dev\sui-lending-bot\data\schema.sql) - Modify PRIMARY KEY, add columns
2. [pebble_reader.py](c:\Dev\sui-lending-bot\data\pebble\pebble_reader.py) - Keep market info, remove deduplication
3. [protocol_merger.py](c:\Dev\sui-lending-bot\data\protocol_merger.py) - Pass market through
4. [position_service.py](c:\Dev\sui-lending-bot\analysis\position_service.py) - Update all queries (lines 423-436, 748-757)
5. [rate_analyzer.py](c:\Dev\sui-lending-bot\analysis\rate_analyzer.py) - Add market parameter to get_rate()
6. [rate_tracker.py](c:\Dev\sui-lending-bot\data\rate_tracker.py) - Store market in snapshots
7. Migration script - Backfill market="default" for existing data

### Verification
1. Run migration script and verify no data loss
2. Verify PRIMARY KEY includes market (sqlite3 .schema rates_snapshot)
3. Create test position with market tracking
4. Verify queries with market parameter work correctly
5. Test backward compatibility with old positions (market="default")

### Recommendation
**Best for: If building from scratch or willing to accept breaking changes**

---

## Approach 3: Composite Names + Metadata Table (Balanced)

### Overview
Use `PebbleMain`/`PebbleXSui`/`PebbleAlt` naming (like Approach 1) BUT add a `protocol_metadata` table to track relationships and enable proper grouping/display.

### Implementation Details

**Step 1:** Create metadata table
```sql
CREATE TABLE protocol_metadata (
    protocol_name VARCHAR(50) PRIMARY KEY,  -- e.g., "PebbleMain"
    base_protocol VARCHAR(50) NOT NULL,     -- e.g., "Pebble"
    market VARCHAR(50),                     -- e.g., "MainMarket"
    display_name VARCHAR(100),              -- e.g., "Pebble (MainMarket)"
    enabled BOOLEAN DEFAULT TRUE,
    notes TEXT
);

-- Insert metadata for existing protocols
INSERT INTO protocol_metadata (protocol_name, base_protocol, display_name, enabled) VALUES
    ('Navi', 'Navi', 'Navi', TRUE),
    ('AlphaFi', 'AlphaFi', 'AlphaFi', TRUE),
    ('Suilend', 'Suilend', 'Suilend', TRUE),
    ('ScallopLend', 'Scallop', 'Scallop (Lend)', TRUE),
    ('ScallopBorrow', 'Scallop', 'Scallop (Borrow)', TRUE),
    ('PebbleMain', 'Pebble', 'Pebble (MainMarket)', TRUE),
    ('PebbleXSui', 'Pebble', 'Pebble (XSuiMarket)', TRUE),
    ('PebbleAlt', 'Pebble', 'Pebble (AltCoinMarket)', TRUE);
```

**Step 2:** Implement like Approach 1 (split protocol names)
- Follow all steps from Approach 1
- Store composite names in rates_snapshot and positions

**Step 3:** Add metadata queries for display
```python
# In position_service.py or new display layer
def get_display_name(protocol_name):
    cursor.execute("""
        SELECT display_name
        FROM protocol_metadata
        WHERE protocol_name = ?
    """, (protocol_name,))
    return cursor.fetchone()['display_name']

# In protocol_merger filtering logic
def count_unique_protocols(row):
    cursor.execute("""
        SELECT DISTINCT base_protocol
        FROM protocol_metadata
        WHERE protocol_name IN (...)
        AND enabled = TRUE
    """)
    return cursor.fetchall()
```

**Step 4:** Update UI to use display_name
- Position display: JOIN with protocol_metadata to show "Pebble (MainMarket)"
- Strategy analysis: Group by base_protocol

### Pros
- **Clean separation** - protocol storage vs display logic
- **No PRIMARY KEY changes** - uses existing schema
- **Flexible** - easy to add new markets or protocols
- **Proper display** - UI shows "Pebble (MainMarket)" not "PebbleMain"
- **Grouping support** - can query "all Pebble markets" via base_protocol
- **Migration path** - can start with Approach 1, add metadata later
- **Backward compatible** - old protocols get metadata entries too

### Cons
- **New table** - adds complexity
- **JOIN overhead** - display queries need JOIN with metadata
- **Two sources of truth** - protocol name + metadata
- **More maintenance** - CRUD operations for metadata
- **Still inflates count** - protocol list has 3 Pebble entries (but can group)

### Database Impact
- Add protocol_metadata table (new)
- No changes to existing tables
- Optional: add indexes on base_protocol for fast grouping

### Files to Modify
1. [schema.sql](c:\Dev\sui-lending-bot\data\schema.sql) - Add protocol_metadata table
2. [pebble_reader.py](c:\Dev\sui-lending-bot\data\pebble\pebble_reader.py) - Same as Approach 1
3. [protocol_merger.py](c:\Dev\sui-lending-bot\data\protocol_merger.py) - Same as Approach 1 + metadata initialization
4. [position_service.py](c:\Dev\sui-lending-bot\analysis\position_service.py) - Add display_name JOINs for UI
5. [rate_analyzer.py](c:\Dev\sui-lending-bot\analysis\rate_analyzer.py) - Add metadata queries for grouping
6. Migration script - Insert metadata for existing protocols

### Verification
1. Verify protocol_metadata table exists and has all protocols
2. Test JOIN queries for display names
3. Verify filtering groups by base_protocol correctly
4. Create test position and verify display shows "Pebble (MainMarket)"
5. Verify backward compatibility - old protocols display correctly

### Recommendation
**Best for: Long-term solution with clean architecture and migration path from Approach 1**

---

## Approach 4: Virtual Protocol Layer (Most Flexible)

### Overview
Keep storage as "Pebble" with optional market column (nullable, NOT in primary key), add a virtual query layer that handles market-aware operations.

### Implementation Details

**Step 1:** Add nullable market column to rates_snapshot
```sql
ALTER TABLE rates_snapshot ADD COLUMN market VARCHAR(50) DEFAULT NULL;
ALTER TABLE positions ADD COLUMN protocol_A_market VARCHAR(50) DEFAULT NULL;
ALTER TABLE positions ADD COLUMN protocol_B_market VARCHAR(50) DEFAULT NULL;
-- NOTE: market is NOT part of primary key
```

**Step 2:** Modify [pebble_reader.py](c:\Dev\sui-lending-bot\data\pebble\pebble_reader.py)
- Remove deduplication
- Store protocol="Pebble" with market="MainMarket" / "XSuiMarket" / "AltCoinMarket"

**Step 3:** Create ProtocolMarketMapper class
```python
class ProtocolMarketMapper:
    """Translates between storage (protocol, market) and query layer"""

    def get_effective_protocol(self, protocol, market):
        """Pebble + MainMarket → PebbleMain for queries"""
        if protocol == "Pebble" and market:
            return f"Pebble{market.replace('Market', '')}"
        return protocol

    def split_protocol(self, effective_protocol):
        """PebbleMain → (Pebble, MainMarket) for storage"""
        if effective_protocol.startswith("Pebble") and len(effective_protocol) > 6:
            market = effective_protocol[6:] + "Market"
            return "Pebble", market
        return effective_protocol, None
```

**Step 4:** Create RateQueryLayer wrapper
```python
class RateQueryLayer:
    """Wraps position_service queries with market awareness"""

    def query_rates(self, timestamp, protocol, token_contract, market=None):
        if market:
            return self._query_with_market(timestamp, protocol, market, token_contract)
        else:
            return self._query_without_market(timestamp, protocol, token_contract)
```

**Step 5:** Update [position_service.py](c:\Dev\sui-lending-bot\analysis\position_service.py)
- Wrap all rate queries with RateQueryLayer
- Store market in position records (nullable)

### Pros
- **Maximum flexibility** - can query by market or aggregate
- **Backward compatible** - market=NULL for non-Pebble or old data
- **No PRIMARY KEY changes** - market is separate nullable column
- **Incremental adoption** - add market awareness gradually
- **Clean storage** - "Pebble" remains single protocol in storage
- **Best UX** - shows market only when relevant

### Cons
- **High complexity** - virtual layer adds indirection
- **Translation overhead** - every query goes through mapper
- **Two architectures** - storage vs query layer differ
- **Harder to debug** - abstraction obscures what's happening
- **Performance cost** - translation + conditional logic
- **Maintenance burden** - mapper logic to maintain

### Database Impact
- Add nullable market column to rates_snapshot (not in PRIMARY KEY)
- Add nullable market columns to positions (2 columns)
- No breaking changes - existing data works with market=NULL
- Index on market column for performance

### Files to Modify
1. [schema.sql](c:\Dev\sui-lending-bot\data\schema.sql) - Add nullable market columns
2. [pebble_reader.py](c:\Dev\sui-lending-bot\data\pebble\pebble_reader.py) - Populate market column
3. New file: protocol_market_mapper.py - Translation layer
4. New file: rate_query_layer.py - Query wrapper
5. [position_service.py](c:\Dev\sui-lending-bot\analysis\position_service.py) - Use query layer
6. [rate_analyzer.py](c:\Dev\sui-lending-bot\analysis\rate_analyzer.py) - Use query layer
7. [protocol_merger.py](c:\Dev\sui-lending-bot\data\protocol_merger.py) - Handle market dimension

### Verification
1. Test query layer with market=NULL (backward compatibility)
2. Test query layer with market="MainMarket" (Pebble)
3. Verify translation: PebbleMain ↔ (Pebble, MainMarket)
4. Create test position with market tracking
5. Verify performance impact (translation overhead)

### Recommendation
**Best for: If requirements are uncertain and you want maximum flexibility, but accept high complexity**

---

## Comparison Matrix

| Criterion | Approach 1: Split Names | Approach 2: Market Column | Approach 3: Metadata | Approach 4: Virtual Layer |
|-----------|------------------------|---------------------------|---------------------|---------------------------|
| **Implementation Time** | 2-3 hours | 1-2 days | 4-6 hours | 1-2 days |
| **Database Changes** | None | Breaking (PRIMARY KEY) | New table only | Nullable columns |
| **Query Performance** | ✓ Fast | ✓ Fast | ⚠ JOIN overhead | ⚠ Translation overhead |
| **Backward Compatible** | ⚠ Needs migration | ✗ Breaking | ✓ Yes | ✓ Yes |
| **Code Complexity** | ✓ Simple | ⚠ Moderate | ⚠ Moderate | ✗ High |
| **Semantic Correctness** | ⚠ "Protocol" misnomer | ✓ Perfect | ✓ Good | ✓ Good |
| **UI Display** | ⚠ "PebbleMain" | ✓ "Pebble (MainMarket)" | ✓ "Pebble (MainMarket)" | ✓ "Pebble (MainMarket)" |
| **Protocol Count** | ✗ Inflates to 3 | ✓ Stays 1 | ⚠ Storage: 3, Display: 1 | ✓ Stays 1 |
| **Maintainability** | ✓ Simple | ✓ Simple | ⚠ Metadata CRUD | ✗ Complex abstractions |
| **Future Flexibility** | ⚠ Limited | ✓ High | ✓ High | ✓ Maximum |
| **Risk Level** | ✓ Low | ✗ High (data loss risk) | ✓ Low | ⚠ Medium (bugs in layer) |

**Legend:** ✓ Good | ⚠ Moderate | ✗ Poor

---

## Recommended Path Forward

### Immediate Action (This Week)
**Implement Approach 1: Split Protocol Names**

Rationale:
- Prevents invalid cross-market positions NOW
- Zero risk to existing data
- Proven pattern (Scallop already works this way)
- Can be implemented in a few hours
- Buys time to design proper long-term solution

### Long-term Plan (Next Month)
**Migrate to Approach 3: Composite Names + Metadata**

Rationale:
- Approach 1 creates the infrastructure (split protocols)
- Approach 3 adds the metadata layer on top
- Clean migration path: keep storage, add display layer
- Balances correctness with pragmatism
- Flexible for future protocols with markets

### Migration Strategy
```
Week 1: Implement Approach 1
  ↓
Month 2: Add protocol_metadata table
  ↓
Month 2: Update UI to use metadata JOINs
  ↓
Month 3: Refactor filtering to use base_protocol grouping
  ↓
Result: Clean architecture without breaking changes
```

---

## Critical Implementation Notes

### For Any Approach

1. **Backward Compatibility:** Existing positions with protocol="Pebble" need handling
   - Option A: Mark as deprecated, exclude from calculations
   - Option B: Guess market based on tokens (risky)
   - Option C: Leave as-is, only apply new logic to new positions

2. **Protocol Filtering Logic:** Must treat Pebble* as ONE protocol
   - Update [protocol_merger.py](c:\Dev\sui-lending-bot\data\protocol_merger.py):319-327
   - Count unique base protocols, not protocol names

3. **Rate Deduplication:** Do NOT deduplicate by rate anymore
   - Each market has independent rates
   - Remove [pebble_reader.py](c:\Dev\sui-lending-bot\data\pebble\pebble_reader.py):368-371

4. **Strategy Analysis:** Update to consider market constraints
   - Can only pair legs within same market
   - [rate_analyzer.py](c:\Dev\sui-lending-bot\analysis\rate_analyzer.py) needs market awareness

5. **Testing:** Create test positions for each market pair
   - PebbleMain → PebbleMain (valid)
   - PebbleMain → PebbleXSui (invalid, should error or warn)
   - PebbleMain → Navi (valid cross-protocol)

---

## Decision Criteria

Choose based on your priorities:

| Priority | Choose |
|----------|--------|
| **Speed to market** | Approach 1 (2-3 hours) |
| **Architectural purity** | Approach 2 (but accept breaking changes) |
| **Balance of speed + quality** | Approach 3 |
| **Maximum future flexibility** | Approach 4 (but accept complexity) |
| **Risk aversion** | Approach 1 or 3 (both low risk) |
| **No database changes** | Approach 1 |
| **Clean data model** | Approach 2 or 3 |

---

## Next Steps

1. **Review this document** and decide which approach fits your timeline and priorities
2. **Consider hybrid approach:** Start with Approach 1, migrate to Approach 3 later
3. **Estimate time:** How much time can you allocate this week vs next month?
4. **Assess risk tolerance:** Breaking changes acceptable?
5. **Plan migration:** How to handle existing "Pebble" positions?

Once you decide, I can create a detailed implementation plan for your chosen approach with step-by-step instructions and code snippets.

---

## Questions for Tomorrow

Before implementation, clarify:

1. **Historical positions:** What should happen to existing positions with protocol="Pebble"?
   - Keep as-is? Mark deprecated? Attempt to infer market?

2. **Display names:** Do users need to see market explicitly, or can it be technical-only?
   - "PebbleMain" vs "Pebble (MainMarket)" vs "Pebble - Main Market"

3. **Time allocation:** How much time can you spend on this?
   - Quick fix (hours) → Approach 1
   - Proper solution (days) → Approach 3

4. **Breaking changes:** Are you willing to accept database schema changes?
   - Yes → Approach 2 is viable
   - No → Approach 1 or 3

5. **Future protocols:** Do you expect other protocols to have multiple markets?
   - Yes → Invest in Approach 2 or 3 for reusability
   - No → Approach 1 is sufficient