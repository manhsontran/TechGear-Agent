"""
Data ingestion script — run once to populate ChromaDB.

Usage:
    python scripts/ingest_data.py [--data-dir data/raw] [--reset]

Options:
    --data-dir  Path to the folder containing raw Markdown files (default: data/raw)
    --reset     Delete the existing collection before ingesting (full re-index)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path so `src` is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rag.chunker import chunk_documents, load_documents
from src.rag.embedder import build_embeddings, ingest_chunks, reset_collection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingest")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest TechGear data into ChromaDB")
    parser.add_argument(
        "--data-dir",
        default="data/raw",
        help="Path to raw data directory (default: data/raw)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing ChromaDB collection before ingesting",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)

    if args.reset:
        logger.info("--reset flag set: dropping existing collection...")
        reset_collection()

    logger.info("Loading documents from '%s'...", data_dir)
    documents = load_documents(data_dir)

    if not documents:
        logger.error("No documents found in '%s'. Aborting.", data_dir)
        sys.exit(1)

    logger.info("Chunking %d documents...", len(documents))
    chunks = chunk_documents(documents)

    logger.info("Building embedding model...")
    embeddings = build_embeddings()

    logger.info("Ingesting %d chunks into ChromaDB...", len(chunks))
    vector_store = ingest_chunks(chunks, embeddings)

    count = vector_store._collection.count()
    logger.info("✅ Ingestion complete! ChromaDB collection now has %d vectors.", count)


if __name__ == "__main__":
    main()
