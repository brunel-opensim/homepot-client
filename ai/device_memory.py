"""Module for managing device memory using ChromaDB."""

import logging
import os
from typing import Any, Dict, List

import chromadb  # type: ignore
import yaml

logger = logging.getLogger(__name__)


class DeviceMemory:
    """Vector memory for device logs and patterns using ChromaDB."""

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize the DeviceMemory with configuration."""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # Resolve chroma_path relative to the config file location
        base_dir = os.path.dirname(os.path.abspath(config_path))
        raw_path = self.config["memory"]["chroma_path"]
        self.chroma_path = os.path.join(base_dir, raw_path)

        self.collection_name = self.config["memory"]["collection_name"]

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=self.chroma_path)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name
        )
        logger.info(f"Device Memory initialized at {self.chroma_path}")

    def add_memory(self, text: str, metadata: Dict[str, Any], memory_id: str) -> None:
        """Add a memory (log entry) to the vector store."""
        try:
            self.collection.add(documents=[text], metadatas=[metadata], ids=[memory_id])
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")

    def query_similar(
        self, query_text: str, n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar memories (patterns) from history."""
        try:
            results = self.collection.query(
                query_texts=[query_text], n_results=n_results
            )

            # Format results
            memories = []
            if results["documents"] and results["metadatas"]:
                for i in range(len(results["documents"][0])):
                    memories.append(
                        {
                            "content": results["documents"][0][i],
                            "metadata": results["metadatas"][0][i],
                            "distance": (
                                results["distances"][0][i]
                                if results["distances"]
                                else 0
                            ),
                        }
                    )
            return memories
        except Exception as e:
            logger.error(f"Memory query failed: {e}")
            return []
