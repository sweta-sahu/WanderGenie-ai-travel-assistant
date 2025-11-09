# Supabase VectorDB Setup Guide

## Step 1: Access Supabase SQL Editor

1. Go to your Supabase Dashboard: https://supabase.com/dashboard
2. Select your project: `hgxvdwqoernoyarjobxe`
3. Click on **SQL Editor** in the left sidebar
4. Click **New Query**

## Step 2: Run the Setup SQL

Copy and paste the following SQL into the editor and click **Run**:

```sql
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
```

## Step 3: Verify Setup

After running the SQL, verify the table was created:

1. Go to **Table Editor** in the left sidebar
2. You should see `poi_facts` in the list of tables
3. Click on it to see the schema

## Step 4: Run the Test Script

Once the table is created, run the Python test script:

```bash
python setup_and_test_vectordb.py
```

This will:
- Insert 8 sample NYC POIs with embeddings
- Test similarity search with various queries
- Test filtered searches

## What Gets Created

### Table: `poi_facts`
- **id**: Unique identifier for each POI
- **name**: Name of the point of interest
- **city**: City where the POI is located
- **coords**: Geographic coordinates (POINT type)
- **booking_required**: Whether booking is needed
- **booking_url**: URL for booking (if applicable)
- **hours_text**: Operating hours
- **tags**: Array of category tags
- **popularity**: Popularity score (0-10)
- **body**: Full description text
- **embedding**: 1536-dimension vector for similarity search
- **created_at/updated_at**: Timestamps

### Indexes
- **poi_facts_embedding_idx**: IVFFlat index for fast vector similarity search
- **poi_facts_city_idx**: B-tree index for city filtering
- **poi_facts_tags_idx**: GIN index for tag array searches

### Function: `match_poi_facts()`
A PostgreSQL function for efficient similarity search with optional filtering.

## Troubleshooting

### Error: "extension vector does not exist"
The pgvector extension might not be enabled. Contact Supabase support or check if your plan includes pgvector.

### Error: "permission denied"
Make sure you're using the service role key in your `.env` file, not the anon key.

### Table not showing up
After running the SQL, you may need to refresh the Supabase dashboard or wait a few seconds for the schema cache to update.

## Next Steps

After setup is complete, you can:
1. Insert more POI data from CSV files
2. Perform semantic searches on POI descriptions
3. Filter results by city, tags, or other attributes
4. Integrate with the WanderGenie AI agents
