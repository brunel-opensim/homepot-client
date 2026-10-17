"""Retrieval grounding for the AI knowledge path (Tier C).

The knowledge path answers how-to/definition questions from documentation. It
used to rely on a fixed list of five docs truncated to 500 characters each
(``SystemKnowledge.get_documentation_context``), so questions outside that list
(e.g. "How do I enrol a device?") had no real source to cite and the model
fabricated file names.

This module builds a small vector index over the whole ``docs/*.md`` corpus
using the same ChromaDB stack as long-term memory (``ai/device_memory.py``).
Each chunk keeps a real ``source`` (repo-relative path) and ``heading`` so the
knowledge prompt can cite actual files and the API can return a trustworthy
``sources`` list.

Design notes (see ``docs/ai-query-routing.md`` section 8.1):

* **Heading-aware chunks** - a markdown section is a natural unit; long
  sections are windowed with overlap so a chunk stays within the embedder's
  effective range.
* **Version-gated (re)indexing** - a content hash over ``(path, size, mtime)``
  decides whether the index is stale, so startup/query cost is a no-op unless a
  doc changed.
* **Injectable embedding** - production uses ChromaDB's default embedder (the
  same one long-term memory already downloads); tests inject a deterministic
  function so they never download a model.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
from typing import Any, Dict, Iterable, List, Optional, Tuple

import chromadb  # type: ignore
import yaml

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_INDEX_VERSION_ID = "__index_version__"


class DocRetriever:
    """Vector index over the project's markdown documentation."""

    def __init__(
        self,
        docs_dir: str,
        config_path: Optional[str] = None,
        embedding_function: Optional[Any] = None,
        chroma_path: Optional[str] = None,
    ) -> None:
        """Initialise the retriever.

        Args:
            docs_dir: Directory holding the ``*.md`` corpus to index.
            config_path: Path to ``config.yaml`` (defaults to the sibling file).
            embedding_function: Optional ChromaDB embedding function. Tests
                inject a deterministic one to avoid downloading a model.
            chroma_path: Explicit ChromaDB path override (mostly for tests).
        """
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        self._config_path = os.path.abspath(config_path)
        with open(self._config_path, "r") as f:
            self.config = yaml.safe_load(f) or {}

        cfg: Dict[str, Any] = self.config.get("docs", {}) or {}
        self.docs_dir = os.path.abspath(docs_dir)
        self.collection_name = str(cfg.get("collection_name", "project_docs"))
        self.distance_metric = str(cfg.get("distance_metric", "cosine"))
        self.n_results = int(cfg.get("n_results", 6))
        # Cutoff on the vector distance; metric-specific (lower = closer).
        # ``None`` disables the cutoff and returns the top-k regardless.
        self.max_distance: Optional[float] = cfg.get("max_distance")
        self.chunk_size = int(cfg.get("chunk_size", 1200))
        self.chunk_overlap = int(cfg.get("chunk_overlap", 150))
        # Bound what any single chunk contributes so one huge doc cannot flood
        # the context. Also applied per file as a soft read cap.
        self.max_chunks_per_doc = int(cfg.get("max_chunks_per_doc", 60))
        self.max_file_bytes = int(cfg.get("max_file_bytes", 2_000_000))

        self._embedding_function = embedding_function
        if chroma_path is not None:
            resolved_path = os.path.abspath(chroma_path)
        else:
            raw_path = str(cfg.get("chroma_path", "data/docs_chroma"))
            resolved_path = os.path.join(os.path.dirname(self._config_path), raw_path)

        self.client = chromadb.PersistentClient(path=resolved_path)
        self.collection = self._open_collection()
        self._index_lock = threading.Lock()

    # -- setup helpers -----------------------------------------------------

    def _open_collection(self) -> Any:
        kwargs: Dict[str, Any] = {
            "name": self.collection_name,
            "metadata": {"hnsw:space": self.distance_metric},
        }
        if self._embedding_function is not None:
            kwargs["embedding_function"] = self._embedding_function
        try:
            collection = self.client.get_or_create_collection(**kwargs)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Opening docs collection without space metadata (%s)", e)
            kwargs.pop("metadata", None)
            collection = self.client.get_or_create_collection(**kwargs)
        return collection

    def _recreate_collection(self) -> Any:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:  # pragma: no cover - collection may not exist yet
            pass
        self.collection = self._open_collection()
        return self.collection

    # -- indexing ----------------------------------------------------------

    def _discover_docs(self) -> List[str]:
        if not os.path.isdir(self.docs_dir):
            logger.warning("Docs directory not found: %s", self.docs_dir)
            return []
        paths: List[str] = []
        for name in sorted(os.listdir(self.docs_dir)):
            if name.lower().endswith(".md"):
                paths.append(os.path.join(self.docs_dir, name))
        return paths

    @staticmethod
    def _rel_source(abs_path: str, docs_dir: str) -> str:
        rel = os.path.relpath(abs_path, os.path.dirname(docs_dir.rstrip("/")))
        return rel.replace(os.sep, "/")

    def _index_version(self) -> str:
        """Hash of every doc's ``(path, size, mtime)`` -- changes with the corpus."""
        digest = hashlib.sha256()
        for path in self._discover_docs():
            try:
                st = os.stat(path)
            except OSError:
                continue
            digest.update(
                f"{path}\x00{st.st_size}\x00{st.st_mtime_ns}\n".encode("utf-8")
            )
        return digest.hexdigest()

    def _chunk_sections(self, text: str) -> List[Tuple[str, str]]:
        """Split markdown ``text`` into ``(heading, body)`` sections."""
        sections: List[Tuple[str, str]] = []
        heading = ""
        buf: List[str] = []
        for line in text.splitlines():
            match = _HEADING_RE.match(line)
            if match:
                body = "\n".join(buf).strip()
                if body or sections:
                    sections.append((heading, body))
                heading = match.group(2).strip()
                buf = []
            else:
                buf.append(line)
        sections.append((heading, "\n".join(buf).strip()))
        return [(h, b) for h, b in sections if b]

    @staticmethod
    def _windows(text: str, size: int, overlap: int) -> Iterable[str]:
        if len(text) <= size:
            yield text
            return
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                newline = text.rfind("\n", start, end)
                if newline > start + size // 2:
                    end = newline
            yield text[start:end].strip()
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)

    def _chunks_for_doc(self, abs_path: str) -> List[Dict[str, Any]]:
        """Build all chunks for one doc with ``source``/``heading`` metadata."""
        try:
            if os.path.getsize(abs_path) > self.max_file_bytes:
                logger.warning("Skipping oversized doc: %s", abs_path)
                return []
            with open(abs_path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as e:  # pragma: no cover - defensive
            logger.warning("Failed to read doc %s: %s", abs_path, e)
            return []

        source = self._rel_source(abs_path, self.docs_dir)
        # The doc title is the first H1; fall back to the file name.
        title = ""
        for match in _HEADING_RE.finditer(text):
            if len(match.group(1)) == 1:
                title = match.group(2).strip()
                break
        if not title:
            title = os.path.splitext(os.path.basename(abs_path))[0]

        chunks: List[Dict[str, Any]] = []
        for section_idx, (heading, body) in enumerate(self._chunk_sections(text)):
            if len(chunks) >= self.max_chunks_per_doc:
                break
            label = heading or title
            for window_idx, window in enumerate(
                self._windows(body, self.chunk_size, self.chunk_overlap)
            ):
                if not window:
                    continue
                content = f"# {label}\n{window}" if label else window
                chunk_id = hashlib.sha256(
                    f"{source}\x00{section_idx}\x00{window_idx}".encode("utf-8")
                ).hexdigest()
                chunks.append(
                    {
                        "id": chunk_id,
                        "content": content,
                        "metadata": {
                            "source": source,
                            "title": title,
                            "heading": label,
                        },
                    }
                )
                if len(chunks) >= self.max_chunks_per_doc:
                    break
        return chunks

    def ensure_indexed(self, force: bool = False) -> bool:
        """(Re)build the index when the corpus changed. Returns True if rebuilt."""
        with self._index_lock:
            version = self._index_version()
            if not force and self._is_current(version):
                return False
            self._rebuild(version)
            return True

    def _is_current(self, version: str) -> bool:
        try:
            if self.collection.count() <= 1:
                return False
            got = self.collection.get(ids=[_INDEX_VERSION_ID])
            metas = got.get("metadatas") or []
            return bool(metas) and metas[0].get("version") == version
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Could not read docs index version: %s", e)
            return False

    def _rebuild(self, version: str) -> None:
        all_chunks: List[Dict[str, Any]] = []
        for path in self._discover_docs():
            all_chunks.extend(self._chunks_for_doc(path))

        self._recreate_collection()
        if all_chunks:
            self.collection.add(
                ids=[c["id"] for c in all_chunks],
                documents=[c["content"] for c in all_chunks],
                metadatas=[c["metadata"] for c in all_chunks],
            )
        self.collection.upsert(
            ids=[_INDEX_VERSION_ID],
            documents=["project documentation index"],
            metadatas=[{"version": version, "chunks": len(all_chunks)}],
        )
        logger.info(
            "Indexed %d documentation chunk(s) from %s",
            len(all_chunks),
            self.docs_dir,
        )

    # -- reads -------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        n_results: Optional[int] = None,
        max_distance: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Return documentation chunks relevant to ``query``.

        Each result is ``{"content", "source", "heading", "distance"}``.
        Returns an empty list when retrieval is unavailable so callers can fall
        back to static context.
        """
        if not query or not query.strip():
            return []
        try:
            self.ensure_indexed()
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Docs indexing failed: %s", e)
            return []

        cutoff = self.max_distance if max_distance is None else max_distance
        n = n_results if n_results is not None else self.n_results
        try:
            results = self.collection.query(query_texts=[query], n_results=n)
        except Exception as e:
            logger.error("Docs retrieval failed: %s", e)
            return []

        ids = (results.get("ids") or [[]])[0]
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        chunks: List[Dict[str, Any]] = []
        for i, doc in enumerate(documents):
            if ids[i] == _INDEX_VERSION_ID:
                continue
            distance = distances[i] if i < len(distances) else None
            if cutoff is not None and distance is not None and distance > cutoff:
                continue
            meta = metadatas[i] if i < len(metadatas) else {}
            chunks.append(
                {
                    "content": doc,
                    "source": meta.get("source", ""),
                    "heading": meta.get("heading", ""),
                    "distance": distance,
                }
            )
        return chunks

    @staticmethod
    def unique_sources(chunks: List[Dict[str, Any]]) -> List[str]:
        """Return ``source`` paths in first-seen order, de-duplicated."""
        seen: List[str] = []
        for chunk in chunks:
            source = chunk.get("source")
            if source and source not in seen:
                seen.append(source)
        return seen

    def get_stats(self) -> Dict[str, Any]:
        """Return basic index statistics (for diagnostics/tests)."""
        try:
            return {
                "chunks": max(self.collection.count() - 1, 0),
                "collection_name": self.collection_name,
                "docs_dir": self.docs_dir,
            }
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Failed to read docs stats: %s", e)
            return {"chunks": 0, "status": "error"}
