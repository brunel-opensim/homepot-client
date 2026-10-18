"""Tests for documentation retrieval grounding (ai/doc_retriever.py).

These exercise the real ChromaDB-backed index with a deterministic embedding
function (no model download) and a throwaway on-disk database, mirroring
``test_ai_memory.py``.
"""

import os
import sys
import zlib

from chromadb.api.types import EmbeddingFunction
import pytest
import yaml

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.doc_retriever import DocRetriever  # noqa: E402

# ChromaDB's native Rust bindings intermittently crash the interpreter with an
# access violation in Collection.add on Windows runners; the retrieval logic is
# platform independent and is still exercised on Linux and macOS.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="ChromaDB native access violation on Windows CI",
)


class BagOfWordsEmbedding(EmbeddingFunction):
    """Deterministic embedding: token counts hashed into a fixed vector."""

    def __init__(self) -> None:
        """Initialise the embedder with a fixed vector dimension."""
        super().__init__()
        self.dim = 256

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


def make_retriever(tmp_path, docs, **overrides):
    """Build a DocRetriever over a temp docs corpus + temp database."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(exist_ok=True)
    for name, content in docs.items():
        (docs_dir / name).write_text(content, encoding="utf-8")

    cfg = {
        "chroma_path": "ignored",
        "collection_name": "test_docs",
        "distance_metric": "cosine",
        "n_results": 5,
        "max_distance": None,
        "chunk_size": 1200,
        "chunk_overlap": 150,
    }
    cfg.update(overrides)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"docs": cfg}))
    return DocRetriever(
        docs_dir=str(docs_dir),
        config_path=str(config_path),
        embedding_function=BagOfWordsEmbedding(),
        chroma_path=str(tmp_path / "chroma"),
    )


ENROL_DOC = """# Device registration

## Enrolment workflow

Create a site, generate a bootstrap key, then the owner claims the key.

## Roles

Operators generate bootstrap keys; owners enrol devices.
"""

ANOMALY_DOC = """# Anomaly detection

## Thresholds

CPU and memory thresholds flag high usage as anomalies.
"""


def test_retrieves_relevant_doc_with_real_source(tmp_path):
    """A keyword query returns the matching doc with its real path."""
    retriever = make_retriever(tmp_path, {"a.md": ENROL_DOC, "b.md": ANOMALY_DOC})

    results = retriever.retrieve("how do I enrol a device with a bootstrap key")

    assert results
    assert results[0]["source"] == "docs/a.md"
    assert "bootstrap key" in results[0]["content"].lower()


def test_chunks_carry_heading_metadata(tmp_path):
    """Chunks expose the section heading they came from."""
    retriever = make_retriever(tmp_path, {"a.md": ENROL_DOC})

    results = retriever.retrieve("enrolment workflow")

    headings = {r["heading"] for r in results}
    assert "Enrolment workflow" in headings
    assert all(r["source"] == "docs/a.md" for r in results)


def test_unique_sources_deduplicates_and_preserves_order():
    """unique_sources keeps first-seen order without duplicates."""
    chunks = [
        {"source": "docs/a.md"},
        {"source": "docs/b.md"},
        {"source": "docs/a.md"},
        {"source": ""},
    ]
    assert DocRetriever.unique_sources(chunks) == ["docs/a.md", "docs/b.md"]


def test_reindexes_when_corpus_changes(tmp_path):
    """Adding a doc invalidates the index so it becomes retrievable."""
    retriever = make_retriever(tmp_path, {"a.md": ENROL_DOC})
    retriever.retrieve("warm the index")

    (tmp_path / "docs" / "c.md").write_text(
        "# Payments\n\n## Billing\n\nInvoices and receipts.", encoding="utf-8"
    )

    assert retriever.ensure_indexed() is True
    results = retriever.retrieve("billing invoices receipts")
    assert any(r["source"] == "docs/c.md" for r in results)


def test_stable_corpus_is_not_reindexed(tmp_path):
    """A second build with no doc change is a no-op."""
    retriever = make_retriever(tmp_path, {"a.md": ENROL_DOC})
    assert retriever.ensure_indexed() is True
    assert retriever.ensure_indexed() is False


def test_empty_or_blank_query_returns_nothing(tmp_path):
    """Blank queries short-circuit without touching the index."""
    retriever = make_retriever(tmp_path, {"a.md": ENROL_DOC})
    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []


def test_max_distance_filters_distant_chunks(tmp_path):
    """A tight distance cutoff drops unrelated chunks."""
    retriever = make_retriever(tmp_path, {"a.md": ENROL_DOC}, max_distance=0.0)
    # Cosine distance is 0 only for an identical vector, so a query that is not
    # an exact token match yields nothing once the cutoff is zero.
    assert retriever.retrieve("completely unrelated phrasing here") == []


def test_long_section_is_windowed(tmp_path):
    """Sections longer than chunk_size are split into overlapping chunks."""
    body = "\n".join(f"line {i} about deployment steps" for i in range(200))
    retriever = make_retriever(
        tmp_path, {"big.md": f"# Big\n\n## Steps\n\n{body}"}, chunk_size=200
    )

    results = retriever.retrieve("deployment steps line")
    assert len(results) > 1


def test_missing_docs_dir_is_safe(tmp_path):
    """A missing docs directory yields an empty index, not a crash."""
    cfg = {
        "collection_name": "test_docs",
        "n_results": 5,
        "max_distance": None,
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"docs": cfg}))
    retriever = DocRetriever(
        docs_dir=str(tmp_path / "does-not-exist"),
        config_path=str(config_path),
        embedding_function=BagOfWordsEmbedding(),
        chroma_path=str(tmp_path / "chroma"),
    )
    assert retriever.retrieve("anything") == []
