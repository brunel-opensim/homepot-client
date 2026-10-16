"""Module for managing device memory using ChromaDB.

This is the AI's **long-term memory**: a persistent vector store of compact,
high-signal records (past answers/incidents) that the assistant can recall by
semantic similarity to ground later answers.

Two things make it safe and useful in a multi-tenant deployment:

1. **Scoping** - every memory is tagged with the ``user_id``/``site_id``/
   ``device_id`` it belongs to, and recall is filtered to the caller's scope
   (see :class:`MemoryScope`). Admins are unrestricted.
2. **Retention** - memories carry a ``created_at`` timestamp and entries older
   than ``retention_days`` are pruned, bounding growth and data-retention risk.

See ``docs/ai-memory.md`` for the full design.
"""

from dataclasses import dataclass, field
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import chromadb  # type: ignore
import yaml

logger = logging.getLogger(__name__)


@dataclass
class MemoryScope:
    """Access scope applied to memory writes and recall.

    Mirrors the RBAC model: memories are tagged with the user/site/device they
    belong to and recall is filtered to the caller's scope. Admins bypass the
    filter entirely.

    Attributes:
        user_id: The authenticated user's numeric id (``None`` for system).
        site_ids: Site ids the caller may see (``None``/empty for none).
        device_id: When set, both the write and recall are device-scoped.
        is_admin: Admins recall across all memories.
    """

    user_id: Optional[int] = None
    site_ids: Optional[List[int]] = field(default=None)
    device_id: Optional[str] = None
    is_admin: bool = False

    def write_metadata(self) -> Dict[str, Any]:
        """Build the scope portion of a memory's metadata."""
        md: Dict[str, Any] = {}
        if self.user_id is not None:
            md["user_id"] = int(self.user_id)
        if self.device_id:
            md["device_id"] = str(self.device_id)
        # A single site lets us tag the memory with a concrete site_id so that
        # site-scoped recall finds it. Multi-site callers fall back to the
        # user_id branch of the recall filter.
        if self.site_ids and len(self.site_ids) == 1:
            md["site_id"] = int(self.site_ids[0])
        return md

    def query_where(self) -> Optional[Dict[str, Any]]:
        """Build the ChromaDB ``where`` clause for recall (``None`` = no filter)."""
        if self.is_admin:
            return None
        # Device-focused questions recall only that device's memories.
        if self.device_id:
            return {"device_id": {"$eq": str(self.device_id)}}
        clauses: List[Dict[str, Any]] = []
        if self.site_ids:
            clauses.append({"site_id": {"$in": [int(s) for s in self.site_ids]}})
        if self.user_id is not None:
            clauses.append({"user_id": {"$eq": int(self.user_id)}})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        # Memories in the caller's sites OR written by the caller.
        return {"$or": clauses}


class DeviceMemory:
    """Vector memory for device logs, incidents and past AI answers."""

    def __init__(
        self,
        config_path: str | None = None,
        embedding_function: Optional[Any] = None,
    ) -> None:
        """Initialize the DeviceMemory with configuration.

        Args:
            config_path: Path to ``config.yaml`` (defaults to the sibling file).
            embedding_function: Optional ChromaDB embedding function (tests
                inject a deterministic one to avoid downloading a model).
        """
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        self._config_path = os.path.abspath(config_path)
        with open(self._config_path, "r") as f:
            self.config = yaml.safe_load(f)

        mem_cfg: Dict[str, Any] = self.config.get("memory", {}) or {}
        self.collection_name = str(mem_cfg.get("collection_name", "device_logs"))
        self.distance_metric = str(mem_cfg.get("distance_metric", "cosine"))
        self.n_results = int(mem_cfg.get("n_results", 5))
        # Cutoff on the vector distance; metric-specific (lower = closer).
        # ``None`` disables the cutoff and returns the top-k regardless.
        self.max_distance: Optional[float] = mem_cfg.get("max_distance")
        self.retention_days: Optional[int] = mem_cfg.get("retention_days")
        self.answer_digest_chars = int(mem_cfg.get("answer_digest_chars", 500))
        self.write_on_query = bool(mem_cfg.get("write_on_query", True))

        self.client = chromadb.PersistentClient(path=self._resolve_path())
        self.collection = self._open_collection(embedding_function)
        # Best-effort retention sweep so growth stays bounded even if no
        # explicit maintenance runs.
        self.prune_older_than()

    # -- setup helpers -----------------------------------------------------

    def _resolve_path(self) -> str:
        base_dir = os.path.dirname(self._config_path)
        raw_path = (self.config.get("memory", {}) or {}).get(
            "chroma_path", "data/chroma_db"
        )
        return os.path.join(base_dir, raw_path)

    def _open_collection(self, embedding_function: Optional[Any]) -> Any:
        kwargs: Dict[str, Any] = {
            "name": self.collection_name,
            "metadata": {"hnsw:space": self.distance_metric},
        }
        if embedding_function is not None:
            kwargs["embedding_function"] = embedding_function
        try:
            collection = self.client.get_or_create_collection(**kwargs)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Opening memory collection without space metadata (%s)", e)
            kwargs.pop("metadata", None)
            collection = self.client.get_or_create_collection(**kwargs)
        return self._ensure_distance_metric(collection, kwargs)

    def _ensure_distance_metric(self, collection: Any, kwargs: Dict[str, Any]) -> Any:
        """Recreate an *empty* collection whose distance space does not match.

        ChromaDB fixes a collection's distance space at creation, so a config
        change (or a collection created before scoping existed) is only picked up
        by recreating it. We only recreate when the collection is empty so we
        never silently drop memories; otherwise we warn and keep the old metric.
        """
        existing = (getattr(collection, "metadata", None) or {}).get("hnsw:space")
        desired = self.distance_metric
        # ChromaDB's default space when unset is "l2".
        if (existing or "l2") == desired:
            return collection
        try:
            if collection.count() == 0:
                self.client.delete_collection(self.collection_name)
                logger.info(
                    "Recreated empty memory collection '%s' with distance space '%s'",
                    self.collection_name,
                    desired,
                )
                return self.client.get_or_create_collection(**kwargs)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Could not recreate memory collection: %s", e)
            return collection
        logger.warning(
            "Memory collection '%s' uses distance space '%s' but config requests "
            "'%s'; the max_distance cutoff may be inaccurate. Delete the memory "
            "store to recreate it with the new metric.",
            self.collection_name,
            existing,
            desired,
        )
        return collection

    # -- writes ------------------------------------------------------------

    def add_memory(self, text: str, metadata: Dict[str, Any], memory_id: str) -> None:
        """Store a memory document (low-level; used by analysis flows)."""
        md = dict(metadata or {})
        md.setdefault("created_at", int(time.time()))
        try:
            self.collection.add(documents=[text], metadatas=[md], ids=[memory_id])
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")

    def remember(
        self,
        text: str,
        scope: Optional[MemoryScope] = None,
        memory_id: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[float] = None,
    ) -> Optional[str]:
        """Store a scoped memory, deduplicated by content.

        Uses ``upsert`` with a deterministic id derived from the content and
        scope, so storing the same record twice does not create duplicates.

        Returns the memory id (or ``None`` on failure).
        """
        metadata: Dict[str, Any] = scope.write_metadata() if scope else {}
        metadata["created_at"] = int(created_at or time.time())
        if extra_metadata:
            metadata.update(extra_metadata)
        if memory_id is None:
            digest = json.dumps(metadata, sort_keys=True, default=str)
            memory_id = hashlib.sha256(
                f"{text}\x00{digest}".encode("utf-8")
            ).hexdigest()
        try:
            self.collection.upsert(
                documents=[text], metadatas=[metadata], ids=[memory_id]
            )
            return memory_id
        except Exception as e:
            logger.error("Failed to store memory: %s", e)
            return None

    def prune_older_than(self, days: Optional[int] = None) -> int:
        """Delete memories older than ``days`` (default: config retention)."""
        retention = self.retention_days if days is None else days
        if not retention:
            return 0
        cutoff = int(time.time()) - int(retention) * 86400
        try:
            result = self.collection.get(where={"created_at": {"$lt": cutoff}})
            ids = result.get("ids") or []
            if ids:
                self.collection.delete(ids=ids)
                logger.info(
                    "Pruned %d memory entr(ies) older than %d days",
                    len(ids),
                    retention,
                )
            return len(ids)
        except Exception as e:
            logger.warning("Memory prune failed: %s", e)
            return 0

    # -- reads -------------------------------------------------------------

    def query_similar(
        self,
        query_text: str,
        n_results: Optional[int] = None,
        where: Optional[Dict[str, Any]] = None,
        max_distance: Optional[float] = None,
        scope: Optional[MemoryScope] = None,
    ) -> List[Dict[str, Any]]:
        """Return memories semantically similar to ``query_text``.

        Args:
            n_results: Max results (defaults to the configured ``n_results``).
            where: Explicit ChromaDB metadata filter. If omitted and ``scope``
                is given, the scope's filter is used.
            max_distance: Distance cutoff; falls back to the configured
                ``max_distance`` (``None`` disables the cutoff).
            scope: Convenience :class:`MemoryScope` for building ``where``.
        """
        if where is None and scope is not None:
            where = scope.query_where()
        cutoff = self.max_distance if max_distance is None else max_distance
        n = n_results if n_results is not None else self.n_results

        kwargs: Dict[str, Any] = {"query_texts": [query_text], "n_results": n}
        if where:
            kwargs["where"] = where
        try:
            results = self.collection.query(**kwargs)
        except Exception as e:
            logger.error(f"Memory query failed: {e}")
            return []

        ids = (results.get("ids") or [[]])[0]
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        memories: List[Dict[str, Any]] = []
        for i, doc in enumerate(documents):
            distance = distances[i] if i < len(distances) else 0
            if cutoff is not None and distance is not None and distance > cutoff:
                continue
            memories.append(
                {
                    "id": ids[i] if i < len(ids) else None,
                    "content": doc,
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distance,
                }
            )
        return memories

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about the stored memories."""
        try:
            count = self.collection.count()
            return {
                "total_memories": count,
                "collection_name": self.collection_name,
                "status": "active",
            }
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {"total_memories": 0, "status": "error"}
