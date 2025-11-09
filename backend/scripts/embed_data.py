"""
Generate embeddings for CSV data files.

This utility reads a CSV file, generates embeddings for specified text columns,
and saves the results to an output file for batch insertion into VectorDB.

Usage:
    python -m backend.scripts.embed_data --input data/poi_facts.csv --output data/poi_facts_embedded.csv
    python -m backend.scripts.embed_data --input data/poi_facts.csv --text-column body --batch-size 50
"""

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from openai import OpenAI
from backend.utils.config import settings
from backend.utils.logger import configure_logging

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings for text data using OpenAI API."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small"
    ):
        """
        Initialize embedding generator.
        
        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Embedding model to use
        """
        self.api_key = api_key or settings.openai_api_key
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        self.total_tokens = 0
        
        logger.info(f"EmbeddingGenerator initialized with model: {model}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * 1536
        
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model
            )
            
            self.total_tokens += response.usage.total_tokens
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    def generate_batch_embeddings(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.
        
        Args:
            texts: List of texts to embed
            show_progress: Whether to show progress bar
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        iterator = tqdm(texts, desc="Generating embeddings") if show_progress else texts
        
        for text in iterator:
            try:
                embedding = self.generate_embedding(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Failed to generate embedding for text: {text[:50]}...")
                # Use zero vector as fallback
                embeddings.append([0.0] * 1536)
        
        return embeddings


def read_csv_file(file_path: str) -> tuple[List[Dict[str, Any]], List[str]]:
    """
    Read CSV file and return rows with fieldnames.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        Tuple of (rows, fieldnames)
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    
    rows = []
    fieldnames = []
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    
    logger.info(f"Read {len(rows)} rows from {file_path}")
    return rows, fieldnames


def write_csv_file(
    file_path: str,
    rows: List[Dict[str, Any]],
    fieldnames: List[str]
):
    """
    Write rows to CSV file.
    
    Args:
        file_path: Output file path
        rows: Rows to write
        fieldnames: Column names
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logger.info(f"Wrote {len(rows)} rows to {file_path}")


def embed_csv_data(
    input_file: str,
    output_file: str,
    text_column: str = "body",
    embedding_column: str = "embedding",
    batch_size: int = 100,
    model: str = "text-embedding-3-small"
) -> Dict[str, Any]:
    """
    Generate embeddings for CSV data and save to output file.
    
    Args:
        input_file: Input CSV file path
        output_file: Output CSV file path
        text_column: Column containing text to embed
        embedding_column: Column name for embeddings
        batch_size: Batch size for processing
        model: Embedding model to use
        
    Returns:
        Summary dictionary
    """
    start_time = time.time()
    
    # Read input file
    logger.info(f"Reading input file: {input_file}")
    rows, fieldnames = read_csv_file(input_file)
    
    if not rows:
        raise ValueError("No data found in input file")
    
    if text_column not in fieldnames:
        raise ValueError(f"Text column '{text_column}' not found in CSV. Available: {fieldnames}")
    
    # Initialize embedding generator
    logger.info("Initializing embedding generator...")
    generator = EmbeddingGenerator(model=model)
    
    # Extract texts
    texts = [row.get(text_column, "") for row in rows]
    
    # Generate embeddings
    logger.info(f"Generating embeddings for {len(texts)} texts...")
    print(f"\nGenerating embeddings for {len(texts)} texts...")
    print(f"Model: {model}")
    print(f"Estimated time: ~{len(texts) * 0.1:.1f}s\n")
    
    embeddings = generator.generate_batch_embeddings(texts, show_progress=True)
    
    # Add embeddings to rows
    if embedding_column not in fieldnames:
        fieldnames.append(embedding_column)
    
    for row, embedding in zip(rows, embeddings):
        # Store embedding as JSON string
        row[embedding_column] = json.dumps(embedding)
    
    # Write output file
    logger.info(f"Writing output file: {output_file}")
    write_csv_file(output_file, rows, fieldnames)
    
    duration = time.time() - start_time
    
    # Calculate estimated cost (text-embedding-3-small: $0.00002 per 1K tokens)
    estimated_cost = (generator.total_tokens / 1000) * 0.00002
    
    summary = {
        "total_rows": len(rows),
        "embeddings_generated": len(embeddings),
        "total_tokens": generator.total_tokens,
        "estimated_cost_usd": round(estimated_cost, 4),
        "duration_seconds": round(duration, 2),
        "output_file": output_file
    }
    
    logger.info(
        f"Embedding generation complete: {len(embeddings)} embeddings, "
        f"{generator.total_tokens} tokens, ${estimated_cost:.4f}, "
        f"took {duration:.2f}s"
    )
    
    return summary


def main():
    """Main entry point for the embedding generation script."""
    parser = argparse.ArgumentParser(
        description="Generate embeddings for CSV data files"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input CSV file path (e.g., data/poi_facts.csv)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output CSV file path (default: input_embedded.csv)"
    )
    parser.add_argument(
        "--text-column",
        type=str,
        default="body",
        help="Column containing text to embed (default: body)"
    )
    parser.add_argument(
        "--embedding-column",
        type=str,
        default="embedding",
        help="Column name for embeddings (default: embedding)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for processing (default: 100)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="text-embedding-3-small",
        help="Embedding model (default: text-embedding-3-small)"
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
    
    # Determine output file
    if not args.output:
        input_path = Path(args.input)
        args.output = str(input_path.parent / f"{input_path.stem}_embedded{input_path.suffix}")
    
    logger.info("=" * 60)
    logger.info("Embedding Generation Script")
    logger.info("=" * 60)
    logger.info(f"Input file: {args.input}")
    logger.info(f"Output file: {args.output}")
    logger.info(f"Text column: {args.text_column}")
    logger.info(f"Embedding column: {args.embedding_column}")
    logger.info(f"Model: {args.model}")
    logger.info("=" * 60)
    
    # Run embedding generation
    try:
        summary = embed_csv_data(
            input_file=args.input,
            output_file=args.output,
            text_column=args.text_column,
            embedding_column=args.embedding_column,
            batch_size=args.batch_size,
            model=args.model
        )
        
        # Print summary
        print("\n" + "=" * 60)
        print("EMBEDDING GENERATION SUMMARY")
        print("=" * 60)
        print(f"Total rows: {summary['total_rows']}")
        print(f"Embeddings generated: {summary['embeddings_generated']}")
        print(f"Total tokens: {summary['total_tokens']}")
        print(f"Estimated cost: ${summary['estimated_cost_usd']:.4f}")
        print(f"Duration: {summary['duration_seconds']}s")
        print(f"Output file: {summary['output_file']}")
        print("=" * 60)
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
