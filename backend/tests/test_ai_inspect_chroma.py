"""Tests for the ChromaDB inspection helper (ai/inspect_chroma.py).

These cover the store-selection logic (``memory`` vs ``docs``) and the
read-only snapshot fallback that lets a non-owner (e.g. ``demouser`` over SSH)
inspect a store the running API already holds. A real ChromaDB store is created
in a throwaway directory so the fallback path is exercised end to end.
"""

import os
import sys
import zlib

from chromadb.api.types import EmbeddingFunction
import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai import inspect_chroma  # noqa: E402

# ChromaDB's native Rust bindings intermittently crash the interpreter with an
# access violation on Windows runners; the logic under test is platform
# independent and is still exercised on Linux and macOS.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="ChromaDB native access violation on Windows CI",
)


class BagOfWordsEmbedding(EmbeddingFunction):
    """Deterministic embedding: token counts hashed into a fixed vector."""

    def __init__(self) -> None:
        """Initialise the embedder with a fixed vector dimension."""
        super().__init__()
        self.dim = 64

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
        return "bag-of-words-inspect-test"


def _make_store(path, collection_name, documents):
    """Create a real on-disk ChromaDB store at ``path``."""
    import chromadb

    client = chromadb.PersistentClient(path=str(path))
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.create_collection(
        collection_name, embedding_function=BagOfWordsEmbedding()
    )
    if documents:
        collection.add(
            ids=[f"id{i}" for i in range(len(documents))],
            documents=documents,
        )
    return collection


def test_store_defaults_resolve_to_known_collections():
    """Each store maps to its configured path and collection."""
    config = {
        "memory": {"chroma_path": "data/chroma_db", "collection_name": "device_logs"},
        "docs": {"chroma_path": "data/docs_chroma", "collection_name": "project_docs"},
    }
    assert inspect_chroma.get_collection_name(config, "memory") == "device_logs"
    assert inspect_chroma.get_collection_name(config, "docs") == "project_docs"

    mem_path = inspect_chroma.get_store_path(config, "memory")
    docs_path = inspect_chroma.get_store_path(config, "docs")
    assert mem_path.endswith(os.path.join("data", "chroma_db"))
    assert docs_path.endswith(os.path.join("data", "docs_chroma"))
    # Paths resolve relative to ai/config.yaml, not the caller's cwd.
    assert os.path.isabs(mem_path) and os.path.isabs(docs_path)


def test_store_falls_back_to_defaults_when_config_section_missing():
    """An empty/absent section still yields a usable store reference."""
    config: dict = {}
    assert inspect_chroma.get_collection_name(config, "docs") == "project_docs"
    assert inspect_chroma.get_collection_name(config, "memory") == "device_logs"


def test_open_client_uses_live_store_when_writable(tmp_path):
    """A writable store opens directly with no snapshot."""
    store = tmp_path / "chroma_db"
    store.mkdir()
    _make_store(store, "device_logs", ["camera failure on pos-01"])

    client, snapshot_dir, used_path = inspect_chroma.open_client(str(store))
    assert snapshot_dir is None
    assert used_path == str(store)
    assert client.get_collection("device_logs").count() == 1


def test_open_client_snapshots_readonly_store(tmp_path, monkeypatch):
    """A failing live open (store held by the API / another user) triggers a copy.

    The live failure is forced by patching ``PersistentClient`` to raise on the
    first call, so this is deterministic across platforms: on Linux the real
    failure is SQLite's "attempt to write a readonly database", but locally
    SQLite can fall back to a read-only open and would not raise.
    """
    import chromadb

    store = tmp_path / "chroma_db"
    store.mkdir()
    _make_store(store, "device_logs", ["camera failure on pos-01", "enrol a device"])

    # Point the snapshot at a fixed dir so cleanup is observable.
    snap_target = tmp_path / "snap"

    def _mkdtemp(**_kwargs):
        snap_target.mkdir()
        return str(snap_target)

    monkeypatch.setattr(
        inspect_chroma.tempfile, "mkdtemp", _mkdtemp
    )

    real_client = chromadb.PersistentClient
    calls = {"n": 0}

    def _fail_first_live(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("attempt to write a readonly database")
        return real_client(**kwargs)

    monkeypatch.setattr(inspect_chroma.chromadb, "PersistentClient", _fail_first_live)

    client, snapshot_dir, used_path = inspect_chroma.open_client(str(store))

    assert snapshot_dir is not None
    assert used_path == snapshot_dir != str(store)
    # The fallback copy is usable and holds the same data.
    assert client.get_collection("device_logs").count() == 2


def test_snapshot_store_copies_readable_files(tmp_path):
    """snapshot_store copies every entry and leaves the copies writable."""
    store = tmp_path / "src"
    (store / "segment").mkdir(parents=True)
    (store / "chroma.sqlite3").write_bytes(b"sqlite-bytes")
    (store / "segment" / "bin").write_bytes(b"segment-bytes")
    os.chmod(store / "chroma.sqlite3", 0o444)

    snap = inspect_chroma.snapshot_store(str(store))
    try:
        assert os.path.isfile(os.path.join(snap, "chroma.sqlite3"))
        assert os.path.isfile(os.path.join(snap, "segment", "bin"))
        # Both the root and nested copies are writable.
        assert os.stat(os.path.join(snap, "chroma.sqlite3")).st_mode & 0o200
        assert os.stat(os.path.join(snap, "segment", "bin")).st_mode & 0o200
    finally:
        import shutil

        shutil.rmtree(snap, ignore_errors=True)
