"""
Seed Neo4j graph database with POI data from Cypher file.

Usage:
    python -m backend.scripts.seed_graphdb --file data/neo4j_seed.cypher
    python -m backend.scripts.seed_graphdb --file data/neo4j_seed.cypher --clear
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.memory.graphdb import GraphDBClient
from backend.utils.config import settings
from backend.utils.logger import configure_logging

logger = logging.getLogger(__name__)


def read_cypher_file(file_path: str) -> List[str]:
    """
    Read and parse Cypher file into individual statements.
    
    Args:
        file_path: Path to Cypher file
        
    Returns:
        List of Cypher statements
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Cypher file not found: {file_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by semicolons and filter out empty statements and comments
    statements = []
    for statement in content.split(';'):
        # Remove comments and whitespace
        lines = []
        for line in statement.split('\n'):
            # Remove single-line comments
            if '//' in line:
                line = line[:line.index('//')]
            line = line.strip()
            if line:
                lines.append(line)
        
        statement_text = ' '.join(lines)
        if statement_text:
            statements.append(statement_text)
    
    logger.info(f"Read {len(statements)} Cypher statements from {file_path}")
    return statements


def clear_database(client: GraphDBClient) -> bool:
    """
    Clear all nodes and relationships from the database.
    
    Args:
        client: GraphDBClient instance
        
    Returns:
        bool: True if successful
    """
    logger.warning("Clearing all data from Neo4j database...")
    
    try:
        # Delete all nodes and relationships
        client.execute_query("MATCH (n) DETACH DELETE n")
        logger.info("Database cleared successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to clear database: {e}")
        return False


def execute_statement_with_transaction(
    client: GraphDBClient,
    statement: str,
    statement_num: int,
    total_statements: int
) -> Dict[str, Any]:
    """
    Execute a single Cypher statement with transaction management.
    
    Args:
        client: GraphDBClient instance
        statement: Cypher statement to execute
        statement_num: Current statement number (for logging)
        total_statements: Total number of statements
        
    Returns:
        Result dictionary with success status and details
    """
    try:
        logger.debug(f"Executing statement {statement_num}/{total_statements}")
        logger.debug(f"Statement: {statement[:100]}...")
        
        result = client.execute_query(statement)
        
        logger.info(
            f"Statement {statement_num}/{total_statements} executed successfully",
            extra={
                "statement_num": statement_num,
                "result_count": len(result) if result else 0
            }
        )
        
        return {
            "success": True,
            "statement_num": statement_num,
            "result_count": len(result) if result else 0,
            "error": None
        }
        
    except Exception as e:
        error_msg = f"Statement {statement_num} failed: {str(e)}"
        logger.error(error_msg, extra={"statement": statement[:200]})
        
        return {
            "success": False,
            "statement_num": statement_num,
            "result_count": 0,
            "error": error_msg
        }


def create_indexes(client: GraphDBClient) -> bool:
    """
    Create indexes and constraints on the graph database for performance optimization.
    
    Args:
        client: GraphDBClient instance
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("Creating indexes and constraints on Neo4j...")
    
    try:
        # Read and execute the index creation Cypher
        migrations_dir = Path(__file__).parent.parent / "migrations"
        index_cypher_path = migrations_dir / "001_create_graphdb_indexes.cypher"
        
        if not index_cypher_path.exists():
            logger.warning(f"Index Cypher file not found: {index_cypher_path}")
            return False
        
        # Read the index statements
        index_statements = read_cypher_file(str(index_cypher_path))
        
        logger.info(f"Executing {len(index_statements)} index/constraint statements...")
        
        success_count = 0
        failed_count = 0
        
        for i, statement in enumerate(index_statements, start=1):
            try:
                client.execute_query(statement)
                success_count += 1
                logger.debug(f"Index statement {i}/{len(index_statements)} executed successfully")
            except Exception as e:
                # Some index creation statements may fail if indexes already exist
                # This is expected and not critical
                failed_count += 1
                logger.debug(f"Index statement {i} failed (may already exist): {e}")
        
        logger.info(
            f"Index creation complete: {success_count} successful, {failed_count} failed/skipped"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")
        return False


def seed_graphdb(
    file_path: str,
    clear_first: bool = False,
    create_indexes_flag: bool = True
) -> Dict[str, Any]:
    """
    Seed GraphDB with data from Cypher file.
    
    Args:
        file_path: Path to Cypher file
        clear_first: Whether to clear database before seeding
        create_indexes_flag: Whether to create indexes after seeding
        
    Returns:
        Summary dictionary with success/failure counts
    """
    start_time = time.time()
    
    # Initialize GraphDB client
    logger.info("Initializing GraphDB client...")
    client = GraphDBClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password
    )
    
    # Connect to database
    logger.info("Connecting to Neo4j...")
    try:
        client.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        return {
            "success": 0,
            "failed": 0,
            "errors": [f"Connection failed: {str(e)}"],
            "duration_seconds": time.time() - start_time
        }
    
    # Clear database if requested
    if clear_first:
        if not clear_database(client):
            logger.warning("Database clear failed, continuing anyway...")
    
    # Read Cypher file
    logger.info(f"Reading Cypher file: {file_path}")
    try:
        statements = read_cypher_file(file_path)
    except Exception as e:
        logger.error(f"Failed to read Cypher file: {e}")
        client.close()
        return {
            "success": 0,
            "failed": 0,
            "errors": [f"Cypher file read failed: {str(e)}"],
            "duration_seconds": time.time() - start_time
        }
    
    if not statements:
        logger.warning("No statements to execute")
        client.close()
        return {
            "success": 0,
            "failed": 0,
            "errors": ["No statements found in Cypher file"],
            "duration_seconds": time.time() - start_time
        }
    
    # Execute statements
    logger.info(f"Executing {len(statements)} Cypher statements...")
    
    success_count = 0
    failed_count = 0
    errors = []
    
    for i, statement in enumerate(statements, start=1):
        result = execute_statement_with_transaction(
            client, statement, i, len(statements)
        )
        
        if result['success']:
            success_count += 1
        else:
            failed_count += 1
            errors.append(result['error'])
        
        # Progress indicator every 10 statements
        if i % 10 == 0:
            logger.info(f"Progress: {i}/{len(statements)} statements executed")
    
    # Create indexes if requested and seeding was successful
    if create_indexes_flag and success_count > 0:
        logger.info("Creating indexes for performance optimization...")
        create_indexes(client)
    
    # Close connection
    client.close()
    
    duration = time.time() - start_time
    
    # Summary
    summary = {
        "total_statements": len(statements),
        "success": success_count,
        "failed": failed_count,
        "errors": errors[:10],  # Limit to first 10 errors
        "duration_seconds": round(duration, 2)
    }
    
    logger.info(
        f"Seeding complete: {success_count} successful, {failed_count} failed, "
        f"took {duration:.2f}s"
    )
    
    return summary


def main():
    """Main entry point for the seeding script."""
    parser = argparse.ArgumentParser(
        description="Seed Neo4j graph database with POI data from Cypher file"
    )
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Path to Cypher file (e.g., data/neo4j_seed.cypher)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all existing data before seeding"
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
    logger.info("GraphDB Seeding Script")
    logger.info("=" * 60)
    logger.info(f"File: {args.file}")
    logger.info(f"Clear database first: {args.clear}")
    logger.info("=" * 60)
    
    # Confirm if clearing database
    if args.clear:
        print("\nWARNING: This will delete all existing data in the database!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Aborted.")
            sys.exit(0)
    
    # Run seeding
    try:
        summary = seed_graphdb(
            file_path=args.file,
            clear_first=args.clear,
            create_indexes_flag=not args.no_indexes
        )
        
        # Print summary
        print("\n" + "=" * 60)
        print("SEEDING SUMMARY")
        print("=" * 60)
        print(f"Total statements: {summary['total_statements']}")
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
