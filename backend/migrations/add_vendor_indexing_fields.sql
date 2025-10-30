-- Migration: Add indexing status fields to vendors table
-- Date: 2025-10-30
-- Description: Add is_indexed and last_indexed_at columns to track Qdrant synchronization

-- Add is_indexed column (default FALSE for existing rows)
ALTER TABLE vendors
ADD COLUMN IF NOT EXISTS is_indexed BOOLEAN NOT NULL DEFAULT FALSE;

-- Add last_indexed_at column
ALTER TABLE vendors
ADD COLUMN IF NOT EXISTS last_indexed_at TIMESTAMP WITH TIME ZONE;

-- Create index on is_indexed for faster queries
CREATE INDEX IF NOT EXISTS idx_vendors_is_indexed ON vendors(is_indexed);

-- Set existing vendors as not indexed (explicit update)
UPDATE vendors SET is_indexed = FALSE WHERE is_indexed IS NULL;

-- Log migration completion
DO $$
BEGIN
  RAISE NOTICE 'Migration completed: Added is_indexed and last_indexed_at columns to vendors table';
END $$;
