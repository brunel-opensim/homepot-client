#!/usr/bin/env python3
"""Utility script to inspect ChromaDB contents."""

import argparse
import os
import sys
from typing import Any, Dict

import chromadb  # type: ignore
import yaml

# Default paths
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "ai", "config.yaml")


def load_config() -> Dict[str, Any]:
    """Load configuration from yaml file."""
    if not os.path.exists(CONFIG_PATH):
        print(f"Error: Config file not found at {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)  # type: ignore


def get_db_path(config: Dict[str, Any]) -> str:
    """Get the absolute path to the ChromaDB database."""
    # Resolve chroma_path relative to the config file location
    base_dir = os.path.dirname(CONFIG_PATH)
    raw_path = config.get("memory", {}).get("chroma_path", "data/chroma_db")
    return os.path.join(base_dir, raw_path)


def get_collection_name(config: Dict[str, Any]) -> str:
    """Get the collection name from config."""
    return config.get("memory", {}).get("collection_name", "device_logs")  # type: ignore


def format_metadata(metadata: Dict[str, Any]) -> str:
    """Format metadata dictionary as a string."""
    return ", ".join(f"{k}={v}" for k, v in metadata.items())


def main() -> None:
    """Execute the main entry point for the script."""
    parser = argparse.ArgumentParser(description="Inspect ChromaDB contents")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List collections
    subparsers.add_parser("list", help="List all collections")

    # Count items
    subparsers.add_parser("count", help="Count items in the default collection")

    # Peek items
    peek_parser = subparsers.add_parser("peek", help="View the first N items")
    peek_parser.add_argument(
        "-n", "--limit", type=int, default=5, help="Number of items to view"
    )

    # Query items
    query_parser = subparsers.add_parser("query", help="Search for similar items")
    query_parser.add_argument("text", type=str, help="Text to search for")
    query_parser.add_argument(
        "-n", "--limit", type=int, default=3, help="Number of results"
    )

    # Dump all (use with caution)
    subparsers.add_parser("dump", help="Dump all items (ID and Metadata only)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config()
    db_path = get_db_path(config)
    collection_name = get_collection_name(config)

    if not os.path.exists(db_path):
        print(f"Error: ChromaDB database not found at {db_path}")
        print("Has the AI service been run yet?")
        sys.exit(1)

    try:
        client = chromadb.PersistentClient(path=db_path)
    except Exception as e:
        print(f"Error connecting to ChromaDB: {e}")
        sys.exit(1)

    if args.command == "list":
        collections = client.list_collections()
        print(f"Collections in {db_path}:")
        for col in collections:
            print(f" - {col.name}")

    else:
        # For other commands, we need the specific collection
        try:
            collection = client.get_collection(collection_name)
        except Exception:
            print(f"Error: Collection '{collection_name}' not found.")
            print("Available collections:")
            for col in client.list_collections():
                print(f" - {col.name}")
            sys.exit(1)

        if args.command == "count":
            count = collection.count()
            print(f"Collection: {collection_name}")
            print(f"Total items: {count}")

        elif args.command == "peek":
            results = collection.peek(limit=args.limit)
            print(f"Peeking top {args.limit} items from '{collection_name}':")
            if not results["ids"]:
                print("No items found.")
            else:
                for i, _id in enumerate(results["ids"]):
                    print(f"\n[{i + 1}] ID: {_id}")
                    if results["metadatas"]:
                        print(f"    Metadata: {results['metadatas'][i]}")
                    if results["documents"]:
                        print(f"    Document: {results['documents'][i]}")

        elif args.command == "query":
            print(f"Searching for: '{args.text}' in '{collection_name}'...")
            results = collection.query(query_texts=[args.text], n_results=args.limit)  # type: ignore

            if not results["ids"] or not results["ids"][0]:
                print("No matches found.")
            else:
                for i, _id in enumerate(results["ids"][0]):
                    print(f"\n[{i + 1}] ID: {_id}")
                    # type: ignore
                    print(f"    Distance: {results['distances'][0][i]:.4f}")  # type: ignore
                    if results["metadatas"]:
                        print(f"    Metadata: {results['metadatas'][0][i]}")  # type: ignore
                    if results["documents"]:
                        print(f"    Document: {results['documents'][0][i]}")

        elif args.command == "dump":
            # Get all data
            count = collection.count()
            if count == 0:
                print("Collection is empty.")
            else:
                results = collection.get()  # type: ignore
                print(f"Dumping all {count} items from '{collection_name}':")
                for i, _id in enumerate(results["ids"]):
                    print(f"[{i + 1}] ID: {_id} | Metadata: {results['metadatas'][i]}")  # type: ignore


if __name__ == "__main__":
    main()
