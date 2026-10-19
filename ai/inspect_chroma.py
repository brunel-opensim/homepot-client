#!/usr/bin/env python3
"""Utility script to inspect ChromaDB contents.

Two stores are supported (see ``ai/config.yaml``):

* ``memory`` -> ``data/chroma_db`` / collection ``device_logs``
  (long-term AI memory, written by the AI endpoints)
* ``docs``   -> ``data/docs_chroma`` / collection ``project_docs``
  (Tier C documentation index used for grounding)

ChromaDB's ``PersistentClient`` always opens SQLite in read-write mode, so a
second process cannot open a store that the running API already holds (or that
is owned by another user). When that happens this tool transparently copies the
store into a temporary directory and inspects the copy, printing a notice that
the numbers are a snapshot.
"""

import argparse
import os
import shutil
import sys
import tempfile
from typing import Any, Dict, Optional, Tuple

try:
    import chromadb  # type: ignore
    import yaml  # type: ignore
except ModuleNotFoundError as exc:
    sys.exit(
        f"Error: module '{exc.name}' is not installed for {sys.executable}.\n"
        "Run this tool with the project virtualenv:\n"
        "  .venv/bin/python ai/inspect_chroma.py --help\n"
        "or install the dependencies: pip install -r backend/requirements.txt"
    )

# Default paths
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "ai", "config.yaml")

# Known stores: CLI name -> (config section, fallback path, fallback collection)
STORES: Dict[str, Tuple[str, str, str]] = {
    "memory": ("memory", "data/chroma_db", "device_logs"),
    "docs": ("docs", "data/docs_chroma", "project_docs"),
}


def load_config() -> Dict[str, Any]:
    """Load configuration from yaml file."""
    if not os.path.exists(CONFIG_PATH):
        print(f"Error: Config file not found at {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)  # type: ignore


def get_store_path(config: Dict[str, Any], store: str) -> str:
    """Get the absolute path to a ChromaDB store."""
    # Resolve chroma_path relative to the config file location
    base_dir = os.path.dirname(CONFIG_PATH)
    section, fallback_path, _ = STORES[store]
    raw_path = config.get(section, {}).get("chroma_path", fallback_path)
    return os.path.join(base_dir, raw_path)


def get_collection_name(config: Dict[str, Any], store: str) -> str:
    """Get the collection name for a store from config."""
    section, _, fallback_name = STORES[store]
    return config.get(section, {}).get("collection_name", fallback_name)  # type: ignore


def snapshot_store(db_path: str) -> str:
    """Copy a ChromaDB store into a temp dir so it can be opened read-write.

    Returns the path of the copy. The caller owns this directory and should
    remove it when done.
    """
    tmp_dir = tempfile.mkdtemp(prefix="homepot_chroma_snapshot_")
    for entry in os.listdir(db_path):
        src = os.path.join(db_path, entry)
        dst = os.path.join(tmp_dir, entry)
        if os.path.isdir(src):
            shutil.copytree(src, dst, symlinks=True)
        else:
            shutil.copy2(src, dst)
    # copy2 preserves the source mode; if the store is owned by another user
    # the copy would stay read-only and Chroma would fail to open it again.
    for root, _dirs, files in os.walk(tmp_dir):
        os.chmod(root, 0o700)
        for name in files:
            os.chmod(os.path.join(root, name), 0o600)
    return tmp_dir


def open_client(db_path: str) -> Tuple[Any, Optional[str], str]:
    """Open a ChromaDB client, falling back to a snapshot copy if needed.

    Returns ``(client, snapshot_dir_or_None, db_path_used)``.
    """
    try:
        client = chromadb.PersistentClient(path=db_path)
        return client, None, db_path
    except Exception as live_error:
        try:
            snap_dir = snapshot_store(db_path)
        except Exception as snap_error:
            print(f"Error connecting to ChromaDB: {live_error}")
            print(f"Error creating snapshot copy: {snap_error}")
            sys.exit(1)
        try:
            client = chromadb.PersistentClient(path=snap_dir)
        except Exception as snap_client_error:
            shutil.rmtree(snap_dir, ignore_errors=True)
            print(f"Error connecting to ChromaDB: {live_error}")
            print(f"Error opening snapshot copy: {snap_client_error}")
            sys.exit(1)
        print(
            "Note: the live store could not be opened "
            f"({live_error}); inspecting a snapshot copy instead."
        )
        return client, snap_dir, snap_dir


def format_metadata(metadata: Dict[str, Any]) -> str:
    """Format metadata dictionary as a string."""
    return ", ".join(f"{k}={v}" for k, v in metadata.items())


def main() -> None:
    """Execute the main entry point for the script."""
    parser = argparse.ArgumentParser(description="Inspect ChromaDB contents")
    parser.add_argument(
        "--store",
        choices=sorted(STORES.keys()),
        default="memory",
        help="Which store to inspect (default: memory)",
    )
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
    store: str = args.store
    db_path = get_store_path(config, store)
    collection_name = get_collection_name(config, store)

    if not os.path.exists(db_path):
        print(f"Error: ChromaDB database not found at {db_path}")
        print("Has the AI service been run yet?")
        sys.exit(1)

    client, snapshot_dir, used_path = open_client(db_path)
    if used_path != db_path:
        print(f"Snapshot copy: {used_path}")

    try:
        if args.command == "list":
            collections = client.list_collections()
            print(f"Collections in {used_path}:")
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
                results = collection.query(  # type: ignore
                    query_texts=[args.text], n_results=args.limit
                )

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
                        print(
                            f"[{i + 1}] ID: {_id} | Metadata: {results['metadatas'][i]}"  # type: ignore
                        )
    finally:
        if snapshot_dir:
            shutil.rmtree(snapshot_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
