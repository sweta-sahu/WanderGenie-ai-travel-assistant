-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create poi_facts table for vector search
CREATE TABLE IF NOT EXISTS poi_facts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    coords POINT,
    booking_required BOOLEAN DEFAULT FALSE,
    booking_url TEXT,
    hours_text TEXT,
    tags TEXT[],
    popularity FLOAT,
    body TEXT NOT NULL,
    embedding VECTOR(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on embedding column for faster similarity search
CREATE INDEX IF NOT EXISTS poi_facts_embedding_idx ON poi_facts 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create index on city for filtering
CREATE INDEX IF NOT EXISTS poi_facts_city_idx ON poi_facts(city);

-- Create index on tags for filtering
CREATE INDEX IF NOT EXISTS poi_facts_tags_idx ON poi_facts USING GIN(tags);

-- Create function for similarity search
CREATE OR REPLACE FUNCTION match_poi_facts(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 10,
    filter_city TEXT DEFAULT NULL
)
RETURNS TABLE (
    id TEXT,
    name TEXT,
    city TEXT,
    body TEXT,
    tags TEXT[],
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        poi_facts.id,
        poi_facts.name,
        poi_facts.city,
        poi_facts.body,
        poi_facts.tags,
        1 - (poi_facts.embedding <=> query_embedding) AS similarity
    FROM poi_facts
    WHERE 
        (filter_city IS NULL OR poi_facts.city = filter_city)
        AND 1 - (poi_facts.embedding <=> query_embedding) > match_threshold
    ORDER BY poi_facts.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Grant permissions (adjust as needed)
-- ALTER TABLE poi_facts ENABLE ROW LEVEL SECURITY;
