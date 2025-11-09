// Migration: Create indexes for GraphDB (Neo4j)
// Purpose: Optimize query performance for node lookups and relationship traversals
// Requirements: 8.2, 8.3

// ============================================================================
// NODE PROPERTY INDEXES
// ============================================================================

// City node indexes
CREATE INDEX city_name_idx IF NOT EXISTS
FOR (c:City) ON (c.name);

CREATE INDEX city_country_idx IF NOT EXISTS
FOR (c:City) ON (c.country);

// Neighborhood node indexes
CREATE INDEX neighborhood_name_idx IF NOT EXISTS
FOR (n:Neighborhood) ON (n.name);

CREATE INDEX neighborhood_city_idx IF NOT EXISTS
FOR (n:Neighborhood) ON (n.city);

// POI node indexes
CREATE INDEX poi_id_idx IF NOT EXISTS
FOR (p:POI) ON (p.id);

CREATE INDEX poi_name_idx IF NOT EXISTS
FOR (p:POI) ON (p.name);

CREATE INDEX poi_category_idx IF NOT EXISTS
FOR (p:POI) ON (p.category);

// Composite index for POI lat/lon (for spatial queries)
CREATE INDEX poi_coordinates_idx IF NOT EXISTS
FOR (p:POI) ON (p.lat, p.lon);

// TicketProvider node indexes
CREATE INDEX ticket_provider_name_idx IF NOT EXISTS
FOR (tp:TicketProvider) ON (tp.name);

CREATE INDEX ticket_provider_booking_type_idx IF NOT EXISTS
FOR (tp:TicketProvider) ON (tp.booking_type);

// ============================================================================
// FULL-TEXT SEARCH INDEXES
// ============================================================================

// Full-text index for POI names (useful for fuzzy search)
CREATE FULLTEXT INDEX poi_name_fulltext_idx IF NOT EXISTS
FOR (p:POI) ON EACH [p.name];

// Full-text index for neighborhood names
CREATE FULLTEXT INDEX neighborhood_name_fulltext_idx IF NOT EXISTS
FOR (n:Neighborhood) ON EACH [n.name];

// ============================================================================
// CONSTRAINTS (Uniqueness)
// ============================================================================

// Ensure POI IDs are unique
CREATE CONSTRAINT poi_id_unique IF NOT EXISTS
FOR (p:POI) REQUIRE p.id IS UNIQUE;

// Ensure City names are unique per country
CREATE CONSTRAINT city_name_country_unique IF NOT EXISTS
FOR (c:City) REQUIRE (c.name, c.country) IS UNIQUE;

// Ensure TicketProvider names are unique
CREATE CONSTRAINT ticket_provider_name_unique IF NOT EXISTS
FOR (tp:TicketProvider) REQUIRE tp.name IS UNIQUE;

// ============================================================================
// RELATIONSHIP INDEXES (Neo4j 5.0+)
// ============================================================================

// Index on NEAR relationship distance property for range queries
// Note: Relationship property indexes require Neo4j 5.0+
// If using older version, comment out these lines
CREATE INDEX near_distance_idx IF NOT EXISTS
FOR ()-[r:NEAR]-() ON (r.distance_km);

// Index on SIMILAR_TO relationship score property
CREATE INDEX similar_to_score_idx IF NOT EXISTS
FOR ()-[r:SIMILAR_TO]-() ON (r.score);

// Index on REQUIRES_TICKET relationship advance_days property
CREATE INDEX requires_ticket_advance_days_idx IF NOT EXISTS
FOR ()-[r:REQUIRES_TICKET]-() ON (r.advance_days);

// ============================================================================
// VERIFICATION QUERIES
// ============================================================================

// To verify indexes are created, run:
// SHOW INDEXES;

// To check if indexes are being used, run EXPLAIN or PROFILE on your queries:
// EXPLAIN
// MATCH (p:POI {id: 'some-id'})
// RETURN p;

// Expected output should show "NodeIndexSeek" or "NodeUniqueIndexSeek"

// To check index statistics:
// CALL db.indexes();

// ============================================================================
// PERFORMANCE NOTES
// ============================================================================

// 1. Indexes speed up read queries but slow down write operations
// 2. Only create indexes on properties that are frequently queried
// 3. Composite indexes are useful for queries that filter on multiple properties
// 4. Full-text indexes enable fuzzy matching and text search
// 5. Constraints ensure data integrity and automatically create indexes
// 6. Use EXPLAIN/PROFILE to verify indexes are being used in your queries
