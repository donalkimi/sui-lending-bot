-- Migration: Clear allocator_settings for schema update
-- Date: February 10, 2026
-- Reason: Added max_single_allocation_pct constraint to allocator_constraints
--
-- This migration clears all existing settings to prevent conflicts with the new field.
-- Users will need to re-save their presets, but this ensures clean schema compatibility.

-- Delete all existing allocator settings
DELETE FROM allocator_settings;

-- Log completion (PostgreSQL only - will be ignored by SQLite)
-- SELECT 'Migration complete: allocator_settings cleared' AS status;
