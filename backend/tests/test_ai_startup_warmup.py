"""Startup AI warm-up: LLM prefix cache + docs index freshness.

``warm_up_llm`` runs at startup as a fire-and-forget task and does two things:
it primes Ollama's KV cache with the real system prompt, and it rebuilds the
docs vector index when the documentation corpus changed.

The docs step matters because the rebuild is otherwise billed to a user. Every
knowledge query checks the corpus version hash first (~2.5 ms on the demo host)
but re-embeds the *whole* corpus inline when it moved - 100.4 s for 3,221 chunks
- and that happens inside whoever asked the first question after the edit. The
warm-up moves it onto the deploy instead.

See docs/ai-doc-retrieval.md ("Operations") and backend/src/homepot/app/main.py.
"""

from homepot.app.api.API_v1.Endpoints import AIEndpoint
from homepot.app.main import app, warm_up_llm


class FakeRetriever:
    """Stands in for ``DocRetriever``: records, and can fail, on demand."""

    def __init__(self, error: Exception = None) -> None:
        """Optionally carry an exception to raise when indexing is attempted."""
        self.calls = 0
        self.error = error

    def ensure_indexed(self, force: bool = False) -> bool:
        """Count the call; raise the configured error if one was given."""
        self.calls += 1
        if self.error is not None:
            raise self.error
        return True


def _stub_llm(monkeypatch, reachable: bool = True) -> None:
    """Replace the Ollama health check and generation (no server needed)."""
    from ai.llm import LLMService

    monkeypatch.setattr(
        LLMService, "check_health", lambda self: reachable, raising=True
    )
    monkeypatch.setattr(
        LLMService,
        "generate_response",
        lambda self, prompt, context=None, system_prompt=None: "ready",
        raising=True,
    )


async def _run_warmup() -> None:
    """Trigger the startup handler and await the task it spawns."""
    await warm_up_llm()
    task = getattr(app.state, "llm_warmup_task", None)
    assert task is not None, "startup warm-up did not schedule its task"
    await task  # surfaces anything the handler swallowed past its guard


async def test_docs_index_is_warmed_at_startup(monkeypatch):
    """A changed corpus is re-embedded at startup, not during a query."""
    retriever = FakeRetriever()
    monkeypatch.setattr(AIEndpoint, "get_doc_retriever", lambda: retriever)
    _stub_llm(monkeypatch, reachable=True)

    await _run_warmup()

    assert retriever.calls == 1


async def test_docs_index_warm_is_skipped_without_ollama(monkeypatch):
    """No LLM reachable -> no docs warm-up.

    The gate is the same one the LLM warm-up already uses, and it keeps CI (no
    Ollama) from embedding the whole docs corpus as a side effect of starting
    the app.
    """
    retriever = FakeRetriever()
    monkeypatch.setattr(AIEndpoint, "get_doc_retriever", lambda: retriever)
    _stub_llm(monkeypatch, reachable=False)

    await _run_warmup()

    assert retriever.calls == 0


async def test_docs_index_warm_failure_is_non_fatal(monkeypatch):
    """A broken index must not fail startup or kill the warm-up task."""
    retriever = FakeRetriever(error=RuntimeError("chroma offline"))
    monkeypatch.setattr(AIEndpoint, "get_doc_retriever", lambda: retriever)
    _stub_llm(monkeypatch, reachable=True)

    await _run_warmup()  # must not raise

    assert retriever.calls == 1
