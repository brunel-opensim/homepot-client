"""Tests for the scoped long-term AI memory (ai/device_memory.py).

These exercise the real ChromaDB-backed store with a deterministic embedding
function (no model download) and a throwaway on-disk database.
"""

import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch
import zlib

from chromadb.api.types import EmbeddingFunction
import pytest
import yaml

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.device_memory import DeviceMemory, MemoryScope  # noqa: E402


class BagOfWordsEmbedding(EmbeddingFunction):
    """Deterministic embedding: token counts hashed into a fixed vector."""

    def __init__(self) -> None:
        """Initialise the embedder with a fixed vector dimension."""
        super().__init__()
        self.dim = 32

    def __call__(self, input):  # type: ignore[override]
        """Embed a batch of texts into bag-of-words vectors."""
        vectors = []
        for text in input:
            vec = [0.0] * self.dim
            for token in str(text).lower().split():
                vec[zlib.crc32(token.encode()) % self.dim] += 1.0
            vectors.append(vec)
        return vectors

    def name(self) -> str:
        """Return the embedder name."""
        return "bag-of-words-test"


def make_memory(tmp_path, **overrides):
    """Build a DeviceMemory backed by a temp config + temp database."""
    mem_cfg = {
        "chroma_path": str(tmp_path / "chroma"),
        "collection_name": "test_memories",
        "distance_metric": "cosine",
        "n_results": 5,
        "max_distance": None,
        "retention_days": None,
        "answer_digest_chars": 200,
        "write_on_query": True,
    }
    mem_cfg.update(overrides)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"memory": mem_cfg}))
    return DeviceMemory(
        config_path=str(config_path), embedding_function=BagOfWordsEmbedding()
    )


def test_remember_and_recall_by_similarity(tmp_path):
    """A stored memory is recalled by semantic similarity."""
    mem = make_memory(tmp_path)
    mem.remember("camera latency spike on site A", MemoryScope(user_id=1))
    mem.remember("printer out of paper in the lobby", MemoryScope(user_id=1))

    results = mem.query_similar("camera latency problem")
    assert results
    assert "camera" in results[0]["content"]


def test_recall_is_site_and_user_scoped(tmp_path):
    """Recall is limited to the caller's sites or their own memories."""
    mem = make_memory(tmp_path)
    mem.remember("camera failure alpha", MemoryScope(user_id=1, site_ids=[5]))
    mem.remember("camera failure beta", MemoryScope(user_id=2, site_ids=[6]))

    site_scope = MemoryScope(user_id=99, site_ids=[5])
    contents = [
        r["content"] for r in mem.query_similar("camera failure", scope=site_scope)
    ]
    assert "camera failure alpha" in contents
    assert "camera failure beta" not in contents

    # The author can always recall their own memory.
    own = MemoryScope(user_id=2, site_ids=[999])
    own_contents = [
        r["content"] for r in mem.query_similar("camera failure", scope=own)
    ]
    assert "camera failure beta" in own_contents
    assert "camera failure alpha" not in own_contents


def test_admin_scope_is_unrestricted(tmp_path):
    """Admins recall memories across every scope."""
    mem = make_memory(tmp_path)
    mem.remember("camera failure alpha", MemoryScope(user_id=1, site_ids=[5]))
    mem.remember("camera failure beta", MemoryScope(user_id=2, site_ids=[6]))

    admin = MemoryScope(user_id=99, site_ids=[], is_admin=True)
    contents = [r["content"] for r in mem.query_similar("camera failure", scope=admin)]
    assert "camera failure alpha" in contents
    assert "camera failure beta" in contents


def test_device_scope_filters_recall(tmp_path):
    """A device-scoped query only recalls that device's memories."""
    mem = make_memory(tmp_path)
    mem.remember("camera offline", MemoryScope(user_id=1, device_id="cam-1"))
    mem.remember("camera offline", MemoryScope(user_id=1, device_id="cam-2"))

    scope = MemoryScope(user_id=1, device_id="cam-1")
    results = mem.query_similar("camera offline", scope=scope)
    assert results
    assert all(r["metadata"].get("device_id") == "cam-1" for r in results)


def test_max_distance_cutoff(tmp_path):
    """Memories beyond max_distance are excluded from recall."""
    mem = make_memory(tmp_path)
    mem.remember("alpha", MemoryScope(user_id=1))

    # No lexical overlap -> large cosine distance -> excluded by a tight cutoff.
    assert mem.query_similar("zeta qqq", max_distance=0.1) == []
    # A permissive cutoff (or None) returns the top-k regardless.
    assert mem.query_similar("zeta qqq", max_distance=None)


def test_remember_deduplicates(tmp_path):
    """Storing the same memory twice keeps a single record."""
    mem = make_memory(tmp_path)
    scope = MemoryScope(user_id=1)
    first = mem.remember("same content", scope)
    second = mem.remember("same content", scope)
    assert first == second
    assert mem.get_memory_stats()["total_memories"] == 1


def test_prune_older_than_removes_expired(tmp_path):
    """Pruning drops memories older than the retention window."""
    mem = make_memory(tmp_path)
    old = time.time() - 40 * 86400
    mem.remember("old memory", MemoryScope(user_id=1), created_at=old)
    mem.remember("fresh memory", MemoryScope(user_id=1))

    removed = mem.prune_older_than(days=30)
    assert removed == 1
    remaining = mem.query_similar("memory", scope=MemoryScope(user_id=1))
    assert [r["content"] for r in remaining] == ["fresh memory"]


def test_empty_collection_recreated_on_metric_change(tmp_path):
    """An empty collection adopts the new distance metric on reopen."""
    make_memory(tmp_path, distance_metric="l2", collection_name="metric_test")
    reopened = make_memory(
        tmp_path, distance_metric="cosine", collection_name="metric_test"
    )
    assert reopened.collection.metadata.get("hnsw:space") == "cosine"


def test_nonempty_collection_keeps_metric(tmp_path):
    """A populated collection is never dropped to change the metric."""
    mem = make_memory(tmp_path, distance_metric="l2", collection_name="keep_test")
    mem.remember("keep me", MemoryScope(user_id=1))

    reopened = make_memory(
        tmp_path, distance_metric="cosine", collection_name="keep_test"
    )
    assert reopened.collection.count() == 1
    assert reopened.collection.metadata.get("hnsw:space") == "l2"


# ── endpoint wiring ─────────────────────────────────────────────────────────


def _authorize_ai_query(app) -> None:
    """Bypass auth for the AI query route in tests."""

    def fake_user() -> dict[str, object]:
        return {"email": "ai-memory@test.local", "role": "Admin", "user_id": 1}

    for route in app.routes:
        if getattr(route, "path", None) != "/api/v1/ai/query":
            continue
        for dependency in route.dependant.dependencies:
            if getattr(dependency.call, "__name__", "") == "user_checker":
                app.dependency_overrides[dependency.call] = fake_user
        return
    raise AssertionError("AI query route not found")


def test_endpoint_persists_and_recalls_scoped_memory():
    """A query recalls with a scope and persists the answer."""
    from fastapi.testclient import TestClient

    from homepot.app.api.API_v1.Endpoints import AIEndpoint
    from homepot.app.main import app

    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = "The fleet is empty."
    mock_knowledge = MagicMock()
    mock_knowledge.get_system_prompt.return_value = "system prompt"
    mock_memory = MagicMock()
    mock_memory.get_memory_stats.return_value = {"total_memories": 0}
    mock_memory.query_similar.return_value = []

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(
            AIEndpoint.ContextBuilder,
            "build_enriched_context",
            AsyncMock(return_value=""),
        ),
    ):
        _authorize_ai_query(app)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/ai/query",
                    json={"query": "What is the system status?"},
                )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200

    # Recall must pass a scope, and the answer must be persisted with a scope.
    assert mock_memory.query_similar.called
    recall_kwargs = mock_memory.query_similar.call_args.kwargs
    assert isinstance(recall_kwargs.get("scope"), MemoryScope)
    assert recall_kwargs["scope"].is_admin is True

    assert mock_memory.remember.called
    remember_kwargs = mock_memory.remember.call_args.kwargs
    assert isinstance(remember_kwargs.get("scope"), MemoryScope)
    assert remember_kwargs["scope"].user_id == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
