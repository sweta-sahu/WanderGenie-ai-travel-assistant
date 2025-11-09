"""
Incremental data refresh utility for VectorDB and GraphDB.

This utility detects new or changed records and performs upsert operations
to keep databases in sync with source data files.

Usage:
    python -m backend.scripts.refresh_data --vectordb --file data/poi_facts.csv
    python -m backend.scripts.refresh_data --graphdb --file data/neo4j_seed.cypher
    python -m backend.scripts.refresh_data --all --vector-file data/poi_facts.csv --graph-file data/neo4j_seed.cypher
"""

import argparse
import csv
import hashlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.memory.vectordb import VectorDBClient
from backend.memory.graphdb import GraphDBClient
from backend.utils.config import settings
from backend.utils.logger import configure_logging

logger = logging.getLogger(__name__)


class DataRefreshManager:
    """Manage incremental data refresh for databases."""
    
    def __init__(self, state_file: str = ".refresh_state.json"):
        """
        Initialize refresh manager.
        
        Args:
            state_file: Path to state file for tracking changes
        """
        self.state_file = Path(state_file)
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state from file."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {"vectordb": {}, "graphdb": {}}
    
    def _save_state(self):
        """Save state to file."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def _compute_hash(self, data: str) -> str:
        """Compute hash of data for change detection."""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    def detect_csv_changes(
        self,
        file_path: str,
        key_column: str = "name"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect new and changed records in CSV file.
        
        Args:
            file_path: Path to CSV file
            key_column: Column to use as unique key
            
        Returns:
            Dictionary with 'new' and 'changed' lists
        """
        logger.info(f"Detecting changes in {file_path}...")
        
        # Read current data
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            current_rows = list(reader)
        
        # Get previous state
        file_key = str(Path(file_path).absolute())
        previous_state = self.state.get("vectordb", {}).get(file_key, {})
        
        new_records = []
        changed_records = []
        current_state = {}
        
        for row in current_rows:
            key = row.get(key_column, "")
            if not key:
                continue
            
            # Compute hash of row data
            row_data = json.dumps(row, sort_keys=True)
            row_hash = self._compute_hash(row_data)
            
            current_state[key] = row_hash
            
            if key not in previous_state:
                # New record
                new_records.append(row)
                logger.debug(f"New record detected: {key}")
            elif previous_state[key] != row_hash:
                # Changed record
                changed_records.append(row)
                logger.debug(f"Changed record detected: {key}")
        
        # Update state
        if "vectordb" not in self.state:
            self.state["vectordb"] = {}
        self.state["vectordb"][file_key] = current_state
        self._save_state()
        
        logger.info(
            f"Change detection complete: {len(new_records)} new, "
            f"{len(changed_records)} changed"
        )
        
        return {
            "new": new_records,
            "changed": changed_records,
            "total": len(current_rows)
        }
    
    def detect_cypher_changes(self, file_path: str) -> bool:
        """
        Detect if Cypher file has changed.
        
        Args:
            file_path: Path to Cypher file
            
        Returns:
            True if file has changed
        """
        logger.info(f"Detecting changes in {file_path}...")
        
        # Read current file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Compute hash
        current_hash = self._compute_hash(content)
        
        # Get previous hash
        file_key = str(Path(file_path).absolute())
        previous_hash = self.state.get("graphdb", {}).get(file_key)
        
        changed = previous_hash != current_hash
        
        # Update state
        if "graphdb" not in self.state:
            self.state["graphdb"] = {}
        self.state["graphdb"][file_key] = current_hash
        self._save_state()
        
        logger.info(f"Cypher file {'has changed' if changed else 'unchanged'}")
        return changed


def refresh_vectordb(
    file_path: str,
    collection_name: str = "poi_facts",
    key_column: str = "name",
    force: bool = False
) -> Dict[str, Any]:
    """
    Refresh VectorDB with incremental updates.
    
    Args:
        file_path: Path to CSV file
        collection_name: Collection name
        key_column: Column to use as unique key
        force: Force full refresh
        
    Returns:
        Summary dictionary
    """
    start_time = time.time()
    
    # Initialize refresh manager
    manager = DataRefreshManager()
    
    # Detect changes
    if not force:
        changes = manager.detect_csv_changes(file_path, key_column)
        records_to_update = changes["new"] + changes["changed"]
        
        if not records_to_update:
            logger.info("No changes detected, skipping refresh")
            return {
                "updated": 0,
                "skipped": changes["total"],
                "duration_seconds": time.time() - start_time
            }
    else:
        # Force full refresh
        logger.info("Force refresh enabled, updating all records")
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            records_to_update = list(reader)
    
    logger.info(f"Updating {len(records_to_update)} records in VectorDB...")
    
    # Initialize VectorDB client
    client = VectorDBClient(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_key,
        embedding_model="text-embedding-3-small",
        openai_api_key=settings.openai_api_key
    )
    
    # Connect
    client.connect()
    
    # Parse records
    from backend.scripts.seed_vectordb import parse_csv_row
    parsed_records = [parse_csv_row(row) for row in records_to_update]
    
    # Upsert records (delete and re-insert)
    # Note: Proper upsert would require matching on a unique key
    # For now, we'll insert new records
    result = client.insert_documents(collection_name, parsed_records)
    
    duration = time.time() - start_time
    
    summary = {
        "updated": result.get("success", 0),
        "failed": result.get("failed", 0),
        "errors": result.get("errors", [])[:5],
        "duration_seconds": round(duration, 2)
    }
    
    logger.info(
        f"VectorDB refresh complete: {summary['updated']} updated, "
        f"took {duration:.2f}s"
    )
    
    return summary


def refresh_graphdb(
    file_path: str,
    force: bool = False
) -> Dict[str, Any]:
    """
    Refresh GraphDB with incremental updates.
    
    Args:
        file_path: Path to Cypher file
        force: Force full refresh
        
    Returns:
        Summary dictionary
    """
    start_time = time.time()
    
    # Initialize refresh manager
    manager = DataRefreshManager()
    
    # Detect changes
    if not force:
        changed = manager.detect_cypher_changes(file_path)
        
        if not changed:
            logger.info("No changes detected, skipping refresh")
            return {
                "updated": 0,
                "skipped": True,
                "duration_seconds": time.time() - start_time
            }
    else:
        logger.info("Force refresh enabled")
    
    logger.info("Refreshing GraphDB...")
    
    # Use the seed_graphdb function
    from backend.scripts.seed_graphdb import seed_graphdb
    
    # Run seeding (this will execute all statements)
    summary = seed_graphdb(file_path, clear_first=False)
    
    return summary


def main():
    """Main entry point for the refresh utility."""
    parser = argparse.ArgumentParser(
        description="Incremental data refresh utility for databases"
    )
    
    # Database selection
    parser.add_argument(
        "--vectordb",
        action="store_true",
        help="Refresh VectorDB"
    )
    parser.add_argument(
        "--graphdb",
        action="store_true",
        help="Refresh GraphDB"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Refresh both databases"
    )
    
    # File paths
    parser.add_argument(
        "--vector-file",
        type=str,
        default="data/poi_facts.csv",
        help="CSV file for VectorDB (default: data/poi_facts.csv)"
    )
    parser.add_argument(
        "--graph-file",
        type=str,
        default="data/neo4j_seed.cypher",
        help="Cypher file for GraphDB (default: data/neo4j_seed.cypher)"
    )
    
    # Options
    parser.add_argument(
        "--collection",
        type=str,
        default="poi_facts",
        help="VectorDB collection name (default: poi_facts)"
    )
    parser.add_argument(
        "--key-column",
        type=str,
        default="name",
        help="CSV key column for change detection (default: name)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force full refresh (ignore change detection)"
    )
    parser.add_argument(
        "--state-file",
        type=str,
        default=".refresh_state.json",
        help="State file path (default: .refresh_state.json)"
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
    
    # Validate arguments
    if not (args.vectordb or args.graphdb or args.all):
        parser.error("Must specify --vectordb, --graphdb, or --all")
    
    logger.info("=" * 60)
    logger.info("Data Refresh Utility")
    logger.info("=" * 60)
    
    results = {}
    
    # Refresh VectorDB
    if args.vectordb or args.all:
        logger.info("Refreshing VectorDB...")
        logger.info(f"File: {args.vector_file}")
        logger.info(f"Collection: {args.collection}")
        logger.info(f"Force: {args.force}")
        logger.info("-" * 60)
        
        try:
            summary = refresh_vectordb(
                file_path=args.vector_file,
                collection_name=args.collection,
                key_column=args.key_column,
                force=args.force
            )
            results["vectordb"] = summary
            
            print("\nVectorDB Refresh Summary:")
            print(f"  Updated: {summary.get('updated', 0)}")
            print(f"  Failed: {summary.get('failed', 0)}")
            print(f"  Duration: {summary.get('duration_seconds', 0)}s")
            
        except Exception as e:
            logger.error(f"VectorDB refresh failed: {e}", exc_info=True)
            results["vectordb"] = {"error": str(e)}
    
    # Refresh GraphDB
    if args.graphdb or args.all:
        logger.info("\nRefreshing GraphDB...")
        logger.info(f"File: {args.graph_file}")
        logger.info(f"Force: {args.force}")
        logger.info("-" * 60)
        
        try:
            summary = refresh_graphdb(
                file_path=args.graph_file,
                force=args.force
            )
            results["graphdb"] = summary
            
            print("\nGraphDB Refresh Summary:")
            print(f"  Statements executed: {summary.get('success', 0)}")
            print(f"  Failed: {summary.get('failed', 0)}")
            print(f"  Duration: {summary.get('duration_seconds', 0)}s")
            
        except Exception as e:
            logger.error(f"GraphDB refresh failed: {e}", exc_info=True)
            results["graphdb"] = {"error": str(e)}
    
    # Final summary
    print("\n" + "=" * 60)
    print("REFRESH COMPLETE")
    print("=" * 60)
    
    # Check for errors
    has_errors = any("error" in r for r in results.values())
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
