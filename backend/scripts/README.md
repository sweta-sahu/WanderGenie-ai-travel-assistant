# Database Seeding Scripts

This directory contains scripts for seeding and refreshing VectorDB (Supabase) and GraphDB (Neo4j) with POI data.

## Scripts Overview

### 1. seed_vectordb.py

Seeds Supabase pgvector with POI facts from CSV files.

**Features:**
- Reads CSV files with POI data
- Generates embeddings using OpenAI API
- Batch insertion with configurable batch size
- Progress logging and error handling
- Creates collection if it doesn't exist

**Usage:**
```bash
# Basic usage
python -m backend.scripts.seed_vectordb --file data/poi_facts.csv

# Custom batch size
python -m backend.scripts.seed_vectordb --file data/poi_facts.csv --batch-size 50

# Custom collection name
python -m backend.scripts.seed_vectordb --file data/poi_facts.csv --collection my_collection

# Skip collection creation (assume it exists)
python -m backend.scripts.seed_vectordb --file data/poi_facts.csv --no-create
```

**CSV Format:**
```csv
city,name,lat,lon,tags,booking_required,booking_url,hours,popularity,body
New York,Statue of Liberty,40.6892,-74.0445,"[""landmark""]",true,https://...,{...},0.98,"Description"
```

### 2. seed_graphdb.py

Seeds Neo4j graph database with POI data from Cypher files.

**Features:**
- Reads Cypher files with CREATE/MERGE statements
- Statement-by-statement execution with transaction management
- Progress logging and error reporting
- Optional database clearing before seeding
- Handles comments and multi-line statements

**Usage:**
```bash
# Basic usage
python -m backend.scripts.seed_graphdb --file data/neo4j_seed.cypher

# Clear database before seeding (WARNING: deletes all data)
python -m backend.scripts.seed_graphdb --file data/neo4j_seed.cypher --clear

# Debug mode
python -m backend.scripts.seed_graphdb --file data/neo4j_seed.cypher --log-level DEBUG
```

**Cypher Format:**
```cypher
// Create nodes
CREATE (poi:POI {
    id: 'statue-of-liberty',
    name: 'Statue of Liberty',
    lat: 40.6892,
    lon: -74.0445
});

// Create relationships
MATCH (p:POI {id: 'statue-of-liberty'}), (n:Neighborhood {name: 'Lower Manhattan'})
CREATE (p)-[:IN_NEIGHBORHOOD]->(n);
```

### 3. embed_data.py

Pre-generates embeddings for CSV files without inserting into database.

**Features:**
- Batch embedding generation with progress bar
- Saves embeddings to output CSV file
- Cost estimation for OpenAI API usage
- Configurable text column and embedding model
- Time estimation

**Usage:**
```bash
# Basic usage (creates poi_facts_embedded.csv)
python -m backend.scripts.embed_data --input data/poi_facts.csv

# Custom output file
python -m backend.scripts.embed_data --input data/poi_facts.csv --output data/embedded.csv

# Custom text column
python -m backend.scripts.embed_data --input data/poi_facts.csv --text-column description

# Different embedding model
python -m backend.scripts.embed_data --input data/poi_facts.csv --model text-embedding-3-large
```

**Use Cases:**
- Pre-generate embeddings to separate API costs from seeding
- Batch process large datasets
- Test embedding quality before insertion
- Create backup with embeddings

### 4. refresh_data.py

Incremental data refresh utility with change detection.

**Features:**
- Detects new and changed records
- Maintains state file for tracking changes
- Upsert functionality for both databases
- Force refresh option
- Separate or combined database refresh

**Usage:**
```bash
# Refresh VectorDB only
python -m backend.scripts.refresh_data --vectordb --vector-file data/poi_facts.csv

# Refresh GraphDB only
python -m backend.scripts.refresh_data --graphdb --graph-file data/neo4j_seed.cypher

# Refresh both databases
python -m backend.scripts.refresh_data --all

# Force full refresh (ignore change detection)
python -m backend.scripts.refresh_data --all --force

# Custom state file location
python -m backend.scripts.refresh_data --all --state-file .my_state.json
```

**Change Detection:**
- VectorDB: Compares hash of each record by key column
- GraphDB: Compares hash of entire Cypher file
- State stored in `.refresh_state.json`

## Workflow Guide

### Initial Setup (First Time)

1. **Seed VectorDB:**
   ```bash
   python -m backend.scripts.seed_vectordb --file data/poi_facts.csv
   ```

2. **Seed GraphDB:**
   ```bash
   python -m backend.scripts.seed_graphdb --file data/neo4j_seed.cypher
   ```

### Regular Updates

1. **Update data files** (edit CSV or Cypher files)

2. **Run incremental refresh:**
   ```bash
   python -m backend.scripts.refresh_data --all
   ```

### Large Dataset Processing

1. **Pre-generate embeddings:**
   ```bash
   python -m backend.scripts.embed_data --input data/large_dataset.csv
   ```

2. **Seed with pre-embedded data:**
   ```bash
   python -m backend.scripts.seed_vectordb --file data/large_dataset_embedded.csv
   ```

## Environment Variables

All scripts require these environment variables (set in `.env` file):

```bash
# OpenTripMap API
OPENTRIPMAP_API_KEY=your_api_key

# Supabase (VectorDB)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_key
SUPABASE_SERVICE_KEY=your_service_key  # For admin operations

# Neo4j (GraphDB)
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# OpenAI (for embeddings)
OPENAI_API_KEY=your_openai_key
```

## Common Options

All scripts support these common options:

| Option | Description | Default |
|--------|-------------|---------|
| `--log-level` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `--help` | Show help message | - |

## Error Handling

All scripts include:
- **Retry logic**: Automatic retry for transient failures
- **Error logging**: Detailed error messages with context
- **Partial success**: Continue processing on individual failures
- **Summary reports**: Success/failure counts and error details

## Performance Tips

1. **Batch Size**: Adjust `--batch-size` based on your data and API limits
   - Smaller batches: More reliable, slower
   - Larger batches: Faster, may hit rate limits

2. **Parallel Processing**: Run VectorDB and GraphDB seeding in parallel
   ```bash
   python -m backend.scripts.seed_vectordb --file data/poi_facts.csv &
   python -m backend.scripts.seed_graphdb --file data/neo4j_seed.cypher &
   wait
   ```

3. **Incremental Updates**: Use `refresh_data.py` for regular updates instead of full re-seeding

4. **Pre-generate Embeddings**: Use `embed_data.py` for large datasets to separate embedding generation from insertion

## Troubleshooting

### Connection Errors

**Problem**: "Failed to connect to Supabase/Neo4j"

**Solutions:**
- Check environment variables are set correctly
- Verify network connectivity
- Check database service status
- Review credentials

### Rate Limiting

**Problem**: OpenAI API rate limit errors

**Solutions:**
- Reduce batch size
- Add delays between batches
- Use pre-generated embeddings
- Upgrade OpenAI API tier

### Memory Issues

**Problem**: Out of memory with large datasets

**Solutions:**
- Process in smaller batches
- Use `embed_data.py` to process separately
- Increase system memory
- Process files in chunks

### Duplicate Records

**Problem**: Records inserted multiple times

**Solutions:**
- Use `refresh_data.py` instead of re-seeding
- Clear database before seeding with `--clear`
- Implement proper unique constraints in database

## Testing

Run tests for seeding scripts:

```bash
# Test VectorDB seeding
pytest tests/test_vectordb_client.py -v

# Test GraphDB seeding
pytest tests/test_graphdb_client.py -v

# Integration tests
pytest tests/integration/ -v
```

## See Also

- [Data Refresh Workflow](../../docs/DATA_REFRESH_WORKFLOW.md)
- [VectorDB Implementation](../../docs/VECTORDB_IMPLEMENTATION.md)
- [GraphDB Implementation](../../docs/GRAPHDB_IMPLEMENTATION.md)
- [Setup Guide](../../docs/SETUP_DATA_LAYER.md)
