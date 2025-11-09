-- Migration: Create indexes for VectorDB (Supabase pgvector)
-- Purpose: Optimize query performance for vector similarity search and filtering
-- Requirements: 8.2, 8.3

-- ============================================================================
-- VECTOR INDEX (HNSW)
-- ============================================================================
-- Create HNSW index on embedding column for fast approximate nearest neighbor search
-- HNSW (Hierarchical Navigable Small World) is optimized for high-dimensional vectors
-- Parameters:
--   m: Maximum number of connections per layer (16 is a good default)
--   ef_construction: Size of dynamic candidate list (64 is a good default)

CREATE INDEX IF NOT EXISTS idx_poi_facts_embedding_hnsw
ON poi_facts
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Note: vector_cosine_ops uses cosine distance for similarity
-- Alternatives: vector_l2_ops (Euclidean), vector_ip_ops (inner product)

-- ============================================================================
-- B-TREE INDEXES
-- ============================================================================
-- Create B-tree index on city column for fast filtering by city
CREATE INDEX IF NOT EXISTS idx_poi_facts_city
ON poi_facts (city);

-- Create B-tree index on name for lookups by POI name
CREATE INDEX IF NOT EXISTS idx_poi_facts_name
ON poi_facts (name);

-- Create B-tree index on booking_required for filtering
CREATE INDEX IF NOT EXISTS idx_poi_facts_booking_required
ON poi_facts (booking_required);

-- ============================================================================
-- GIN INDEX
-- ============================================================================
-- Create GIN (Generalized Inverted Index) on tags array for fast array searches
-- GIN indexes are optimized for array and JSONB data types
CREATE INDEX IF NOT EXISTS idx_poi_facts_tags_gin
ON poi_facts USING gin (tags);

-- ============================================================================
-- COMPOSITE INDEXES
-- ============================================================================
-- Create composite index for common query patterns (city + booking_required)
CREATE INDEX IF NOT EXISTS idx_poi_facts_city_booking
ON poi_facts (city, booking_required);

-- ============================================================================
-- STATISTICS
-- ============================================================================
-- Update table statistics for query planner optimization
ANALYZE poi_facts;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- To verify indexes are created, run:
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'poi_facts';

-- To check if indexes are being used, run EXPLAIN ANALYZE on your queries:
-- EXPLAIN ANALYZE
-- SELECT * FROM poi_facts
-- WHERE city = 'New York City'
-- ORDER BY embedding <-> '[0.1, 0.2, ...]'::vector
-- LIMIT 10;

-- Expected output should show "Index Scan using idx_poi_facts_embedding_hnsw"
