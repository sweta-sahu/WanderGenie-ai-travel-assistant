# Data Refresh Workflow

This document describes the workflow for refreshing data in VectorDB and GraphDB using the incremental update utilities.

## Overview

The data refresh utility (`refresh_data.py`) provides incremental updates to both databases, detecting changes and only updating modified or new records. This is more efficient than full re-seeding for regular updates.

## How It Works

### Change Detection

The refresh utility maintains a state file (`.refresh_state.json`) that tracks:
- **VectorDB**: Hash of each record by key (e.g., POI name)
- **GraphDB**: Hash of the entire Cypher file

When you run a refresh:
1. The utility reads the current data files
2. Compares against the previous state
3. Identifies new or changed records
4. Performs upsert operations only for changed data

### State File

The `.refresh_state.json` file stores:
```json
{
  "vectordb": {
    "/absolute/path/to/poi_facts.csv": {
      "Statue of Liberty": "abc123...",
      "SUMMIT One Vanderbilt": "def456..."
    }
  },
  "graphdb": {
    "/absolute/path/to/neo4j_seed.cypher": "xyz789..."
  }
}
```

## Usage

### Refresh VectorDB Only

```bash
python -m backend.scripts.refresh_data --vectordb --vector-file data/poi_facts.csv
```

This will:
- Detect new or changed records in `poi_facts.csv`
- Generate embeddings for changed records
- Insert/update records in Supabase

### Refresh GraphDB Only

```bash
python -m backend.scripts.refresh_data --graphdb --graph-file data/neo4j_seed.cypher
```

This will:
- Check if the Cypher file has changed
- Execute all statements if changed
- Skip if unchanged

### Refresh Both Databases

```bash
python -m backend.scripts.refresh_data --all \
  --vector-file data/poi_facts.csv \
  --graph-file data/neo4j_seed.cypher
```

### Force Full Refresh

To bypass change detection and update everything:

```bash
python -m backend.scripts.refresh_data --all --force
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--vectordb` | Refresh VectorDB only | - |
| `--graphdb` | Refresh GraphDB only | - |
| `--all` | Refresh both databases | - |
| `--vector-file` | CSV file for VectorDB | `data/poi_facts.csv` |
| `--graph-file` | Cypher file for GraphDB | `data/neo4j_seed.cypher` |
| `--collection` | VectorDB collection name | `poi_facts` |
| `--key-column` | CSV column for unique key | `name` |
| `--force` | Force full refresh | `false` |
| `--state-file` | State file path | `.refresh_state.json` |
| `--log-level` | Logging level | `INFO` |

## Workflow Examples

### Daily Update Workflow

1. **Update source data files**
   ```bash
   # Edit data/poi_facts.csv or data/neo4j_seed.cypher
   ```

2. **Run incremental refresh**
   ```bash
   python -m backend.scripts.refresh_data --all
   ```

3. **Review output**
   ```
   VectorDB Refresh Summary:
     Updated: 5
     Failed: 0
     Duration: 12.3s
   
   GraphDB Refresh Summary:
     Statements executed: 0
     Failed: 0
     Duration: 0.1s
   ```

### Adding New POIs

1. **Add rows to CSV**
   ```csv
   city,name,lat,lon,tags,booking_required,booking_url,hours,popularity,body
   New York,New POI,40.7589,-73.9851,"[""museum""]",false,,,0.85,"Description here"
   ```

2. **Refresh VectorDB**
   ```bash
   python -m backend.scripts.refresh_data --vectordb
   ```

3. **Update Cypher file** (if adding relationships)
   ```cypher
   CREATE (poi:POI {
       id: 'new-poi',
       name: 'New POI',
       lat: 40.7589,
       lon: -73.9851,
       category: 'museum',
       popularity: 0.85
   });
   ```

4. **Refresh GraphDB**
   ```bash
   python -m backend.scripts.refresh_data --graphdb
   ```

### Modifying Existing Data

1. **Edit CSV records**
   - Change description, popularity, or other fields
   - The utility will detect changes by comparing hashes

2. **Run refresh**
   ```bash
   python -m backend.scripts.refresh_data --vectordb
   ```

3. **Only changed records are updated**

## Best Practices

### When to Use Incremental Refresh

- **Daily/weekly updates**: Small changes to existing data
- **Adding new POIs**: A few new records
- **Updating metadata**: Popularity scores, descriptions, hours

### When to Use Full Re-seeding

- **Initial setup**: First time populating databases
- **Major schema changes**: Changing data structure
- **Data corruption**: Need to rebuild from scratch
- **Testing**: Clean slate for testing

### State File Management

- **Commit to version control**: Track what's been deployed
- **Or add to .gitignore**: Keep local state separate
- **Backup before major changes**: In case you need to rollback
- **Delete to force full refresh**: Remove `.refresh_state.json`

### Performance Considerations

- **Batch size**: Default 100 records per batch
- **Embedding cost**: Only changed records generate new embeddings
- **GraphDB**: Full Cypher file execution if any change detected
- **Concurrent updates**: Avoid running multiple refreshes simultaneously

## Troubleshooting

### "No changes detected" but data should update

**Solution**: Delete state file and run with `--force`
```bash
rm .refresh_state.json
python -m backend.scripts.refresh_data --all --force
```

### Embeddings not updating for changed records

**Cause**: The `body` column hasn't changed (embeddings are based on text)

**Solution**: Modify the text content or force regeneration

### GraphDB statements failing

**Cause**: Cypher syntax errors or constraint violations

**Solution**: 
1. Check Cypher file syntax
2. Review error messages in output
3. Test statements individually in Neo4j Browser

### State file conflicts in team environment

**Cause**: Multiple developers with different local states

**Solution**: 
- Add `.refresh_state.json` to `.gitignore`
- Use `--force` for deployments
- Or maintain separate state files per environment

## Integration with CI/CD

### Automated Refresh on Deploy

```yaml
# .github/workflows/deploy.yml
- name: Refresh databases
  run: |
    python -m backend.scripts.refresh_data --all --force
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
    NEO4J_URI: ${{ secrets.NEO4J_URI }}
    NEO4J_USER: ${{ secrets.NEO4J_USER }}
    NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

### Scheduled Refresh

```yaml
# .github/workflows/scheduled-refresh.yml
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Refresh data
        run: python -m backend.scripts.refresh_data --all
```

## Related Scripts

- **seed_vectordb.py**: Full VectorDB seeding from scratch
- **seed_graphdb.py**: Full GraphDB seeding from scratch
- **embed_data.py**: Pre-generate embeddings for CSV files

## See Also

- [VectorDB Implementation](VECTORDB_IMPLEMENTATION.md)
- [GraphDB Implementation](GRAPHDB_IMPLEMENTATION.md)
- [Data Layer Setup](SETUP_DATA_LAYER.md)
