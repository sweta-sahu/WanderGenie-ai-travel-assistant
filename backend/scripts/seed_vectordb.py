"""
Seed Supabase pgvector with POI facts from CSV.

Usage:
    python -m backend.scripts.seed_vectordb --file data/poi_facts.csv
    python -m backend.scripts.seed_vectordb --file data/poi_facts.csv --batch-size 50
    python -m backend.scripts.seed_vectordb --file data/poi_facts.csv --collection custom_collection
"""

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.memory.vectordb import VectorDBClient
from backend.utils.config import settings
from backend.utils.logger import configure_logging

logger = logging.getLogger(__name__)


def parse_json_field(value: str) -> Any:
    """Parse JSON string field from CSV."""
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def parse_csv_row(row: Dict[str, str]) -> Dict[str, Any]:
    """
    Parse a CSV row and convert fields to appropriate types.
    
    Args:
        row: Raw CSV row as dictionary
        
    Returns:
        Parsed row with proper types
    """
    parsed = {}
    
    # Parse each field
    parsed['city'] = row.get('city', '')
    parsed['name'] = row.get('name', '')
    
    # Parse coordinates
    try:
        parsed['lat'] = float(row.get('lat', 0))
        parsed['lon'] = float(row.get('lon', 0))
    except (ValueError, TypeError):
        parsed['lat'] = 0.0
        parsed['lon'] = 0.0
    
    # Parse tags (JSON array)
    parsed['tags'] = parse_json_field(row.get('tags', '[]'))
    
    # Parse booking fields
    booking_required = row.get('booking_required', 'false').lower()
    parsed['booking_required'] = booking_required in ('true', '1', 'yes')
    parsed['booking_url'] = row.get('booking_url', None) or None
    
    # Parse hours (JSON object)
    parsed['hours'] = parse_json_field(row.get('hours', 'null'))
    
    # Parse popularity
    try:
        parsed['popularity'] = float(row.get('popularity', 0))
    except (ValueError, TypeError):
        parsed['popularity'] = 0.0
    
    # Body text for embedding
    parsed['body'] = row.get('body', '')
    
    return parsed


def read_csv_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Read and parse CSV file.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        List of parsed documents
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If CSV is malformed
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    
    documents = []
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader, start=1):
            try:
                parsed = parse_csv_row(row)
                documents.append(parsed)
            except Exception as e:
                logger.warning(
                    f"Failed to parse row {i}: {e}",
                    extra={"row_number": i, "error": str(e)}
                )
                continue
    
    logger.info(f"Read {len(documents)} documents from {file_path}")
    return documents


def batch_documents(documents: List[Dict[str, Any]], batch_size: int) -> List[List[Dict[str, Any]]]:
    """
    Split documents into batches.
    
    Args:
        documents: List of documents
        batch_size: Size of each batch
        
    Returns:
        List of batches
    """
    batches = []
    for i in range(0, len(documents), batch_size):
        batches.append(documents[i:i + batch_size])
    return batches


def create_indexes(client: VectorDBClient, collection_name: str) -> bool:
    """
    Create indexes on the collection for performance optimization.
    
    Args:
        client: VectorDB client instance
        collection_name: Name of collection to create indexes on
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Creating indexes on '{collection_name}'...")
    
    try:
        # Read and execute the index creation SQL
        migrations_dir = Path(__file__).parent.parent / "migrations"
        index_sql_path = migrations_dir / "001_create_vectordb_indexes.sql"
        
        if not index_sql_path.exists():
            logger.warning(f"Index SQL file not found: {index_sql_path}")
            return False
        
        with open(index_sql_path, 'r', encoding='utf-8') as f:
            index_sql = f.read()
        
        # Execute the SQL using Supabase client
        # Note: Supabase Python client doesn't directly support raw SQL execution
        # In production, you would run this via psql or Supabase dashboard
        # For now, we'll log the SQL and recommend manual execution
        
        logger.info("Index creation SQL loaded. Please execute the following SQL manually:")
        logger.info("=" * 60)
        logger.info(index_sql)
        logger.info("=" * 60)
        logger.info("You can execute this via:")
        logger.info("1. Supabase Dashboard > SQL Editor")
        logger.info("2. psql command line")
        logger.info("3. Any PostgreSQL client")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to load index creation SQL: {e}")
        return False


def seed_vectordb(
    file_path: str,
    collection_name: str = "poi_facts",
    batch_size: int = 100,
    create_collection: bool = True,
    create_indexes_flag: bool = True
) -> Dict[str, Any]:
    """
    Seed VectorDB with data from CSV file.
    
    Args:
        file_path: Path to CSV file
        collection_name: Name of collection to create/insert into
        batch_size: Number of documents per batch
        create_collection: Whether to create collection if it doesn't exist
        create_indexes_flag: Whether to create indexes after seeding
        
    Returns:
        Summary dictionary with success/failure counts
    """
    start_time = time.time()
    
    # Initialize VectorDB client
    logger.info("Initializing VectorDB client...")
    client = VectorDBClient(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_key,
        embedding_model="text-embedding-3-small",
        openai_api_key=settings.openai_api_key
    )
    
    # Connect to database
    logger.info("Connecting to Supabase...")
    try:
        client.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        return {
            "success": 0,
            "failed": 0,
            "errors": [f"Connection failed: {str(e)}"],
            "duration_seconds": time.time() - start_time
        }
    
    # Create collection if requested
    if create_collection:
        logger.info(f"Creating collection '{collection_name}'...")
        try:
            schema = {
                "name": "text",
                "city": "text",
                "lat": "float",
                "lon": "float",
                "tags": "jsonb",
                "booking_required": "boolean",
                "booking_url": "text",
                "hours": "jsonb",
                "popularity": "float",
                "body": "text",
                "embedding": "vector(1536)"
            }
            client.create_collection(collection_name, schema)
            logger.info(f"Collection '{collection_name}' created successfully")
        except Exception as e:
            logger.warning(f"Collection creation failed (may already exist): {e}")
    
    # Read CSV file
    logger.info(f"Reading CSV file: {file_path}")
    try:
        documents = read_csv_file(file_path)
    except Exception as e:
        logger.error(f"Failed to read CSV file: {e}")
        return {
            "success": 0,
            "failed": 0,
            "errors": [f"CSV read failed: {str(e)}"],
            "duration_seconds": time.time() - start_time
        }
    
    if not documents:
        logger.warning("No documents to insert")
        return {
            "success": 0,
            "failed": 0,
            "errors": ["No documents found in CSV"],
            "duration_seconds": time.time() - start_time
        }
    
    # Split into batches
    batches = batch_documents(documents, batch_size)
    logger.info(f"Processing {len(documents)} documents in {len(batches)} batches...")
    
    # Insert batches
    total_success = 0
    total_failed = 0
    all_errors = []
    
    for batch_num, batch in enumerate(batches, start=1):
        logger.info(f"Processing batch {batch_num}/{len(batches)} ({len(batch)} documents)...")
        
        try:
            result = client.insert_documents(collection_name, batch)
            total_success += result.get('success', 0)
            total_failed += result.get('failed', 0)
            
            if result.get('errors'):
                all_errors.extend(result['errors'])
            
            logger.info(
                f"Batch {batch_num} complete: {result.get('success', 0)} success, "
                f"{result.get('failed', 0)} failed"
            )
            
        except Exception as e:
            logger.error(f"Batch {batch_num} failed: {e}")
            total_failed += len(batch)
            all_errors.append(f"Batch {batch_num} error: {str(e)}")
    
    # Create indexes if requested
    if create_indexes_flag and total_success > 0:
        logger.info("Creating indexes for performance optimization...")
        create_indexes(client, collection_name)
    
    duration = time.time() - start_time
    
    # Summary
    summary = {
        "total_records": len(documents),
        "success": total_success,
        "failed": total_failed,
        "errors": all_errors[:10],  # Limit to first 10 errors
        "duration_seconds": round(duration, 2)
    }
    
    logger.info(
        f"Seeding complete: {total_success} successful, {total_failed} failed, "
        f"took {duration:.2f}s"
    )
    
    return summary


def main():
    """Main entry point for the seeding script."""
    parser = argparse.ArgumentParser(
        description="Seed Supabase pgvector with POI facts from CSV"
    )
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Path to CSV file (e.g., data/poi_facts.csv)"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="poi_facts",
        help="Collection name (default: poi_facts)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for insertions (default: 100)"
    )
    parser.add_argument(
        "--no-create",
        action="store_true",
        help="Skip collection creation (assume it exists)"
    )
    parser.add_argument(
        "--no-indexes",
        action="store_true",
        help="Skip index creation after seeding"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    configure_logging(log_level=args.log_level)
    
    logger.info("=" * 60)
    logger.info("VectorDB Seeding Script")
    logger.info("=" * 60)
    logger.info(f"File: {args.file}")
    logger.info(f"Collection: {args.collection}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Create collection: {not args.no_create}")
    logger.info("=" * 60)
    
    # Run seeding
    try:
        summary = seed_vectordb(
            file_path=args.file,
            collection_name=args.collection,
            batch_size=args.batch_size,
            create_collection=not args.no_create,
            create_indexes_flag=not args.no_indexes
        )
        
        # Print summary
        print("\n" + "=" * 60)
        print("SEEDING SUMMARY")
        print("=" * 60)
        print(f"Total records: {summary['total_records']}")
        print(f"Successful: {summary['success']}")
        print(f"Failed: {summary['failed']}")
        print(f"Duration: {summary['duration_seconds']}s")
        
        if summary['errors']:
            print(f"\nFirst {len(summary['errors'])} errors:")
            for error in summary['errors']:
                print(f"  - {error}")
        
        print("=" * 60)
        
        # Exit with appropriate code
        sys.exit(0 if summary['failed'] == 0 else 1)
        
    except Exception as e:
        logger.error(f"Seeding failed with exception: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
