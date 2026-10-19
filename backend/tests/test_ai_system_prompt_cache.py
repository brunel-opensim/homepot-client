"""The system prompts every path sends must share one long, stable prefix.

Ollama reuses its key/value cache for the *common prefix* of two prompts: warm,
re-entering a matching prefix costs well under a second, while a cold one costs
tens of seconds for the same token count on the CPU-only host. The startup
warm-up (``backend/src/homepot/app/main.py``) sends the *diagnostic* prompt, so
unless the knowledge prompt starts with those same bytes, the first knowledge
query after startup -- and every switch between the two paths -- pays a full
prompt evaluation of the whole system prompt.

These tests pin that invariant (see ``SystemKnowledge._shared_prefix``): the
shared block must lead every path and must stay byte-identical.
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.system_knowledge import (  # noqa: E402
    _DEFINED_SYSTEM_ROLES,
    SystemKnowledge,
)

# The shared block is the bulk of the system prompt; anything below this means a
# path forked early and the warm-up / path-switch cache reuse is broken.
_MIN_SHARED_CHARS = 10000


def _knowledge():
    return SystemKnowledge(workspace_root)


def _all_prompts(knowledge):
    return {
        "diagnostic": knowledge.get_system_prompt(),
        "knowledge": knowledge.get_knowledge_prompt(),
        "knowledge_repo": knowledge.get_knowledge_prompt(include_repo_tools=True),
    }


def test_every_path_shares_a_long_identical_prefix():
    """Warm-up and every path must agree on the leading bytes."""
    prompts = _all_prompts(_knowledge())
    names = list(prompts)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            shared = os.path.commonprefix([prompts[first], prompts[second]])
            assert len(shared) >= _MIN_SHARED_CHARS, (
                f"{first} and {second} share only {len(shared)} chars of "
                f"prefix; the KV-cache warm-up will not be reused"
            )


def test_shared_prefix_carries_the_static_system_context():
    """The shared block must hold the static grounding, not mode-specific text."""
    knowledge = _knowledge()
    diag = knowledge.get_system_prompt()
    kn = knowledge.get_knowledge_prompt()
    shared = os.path.commonprefix([diag, kn])

    assert shared.startswith("SYSTEM CONTEXT:\n")
    assert knowledge.get_full_system_context() in shared
    assert _DEFINED_SYSTEM_ROLES in shared
    cmd_ref = knowledge.get_command_payload_reference()
    if cmd_ref:
        assert cmd_ref in shared

    # The mode-specific identity is exactly where the two paths fork.
    assert shared.endswith("IDENTITY:\nYou are the HOMEPOT ")
    assert "System Diagnostics AI" in diag[len(shared) :]
    assert "Knowledge Assistant" in kn[len(shared) :]


def test_diagnostic_only_doc_block_stays_out_of_the_shared_prefix():
    """The diagnostic-only [DOCUMENTATION] block must sit in the tail.

    If it crept back into the shared region, the knowledge prompt (which
    deliberately omits it) would fork before the end of the block and lose the
    cache reuse for the whole system context.
    """
    knowledge = _knowledge()
    doc_block = knowledge.get_documentation_context()
    assert doc_block and doc_block.startswith("[DOCUMENTATION]")

    diag = knowledge.get_system_prompt()
    kn = knowledge.get_knowledge_prompt()
    shared = os.path.commonprefix([diag, kn])

    assert doc_block in diag
    assert doc_block not in shared
    assert doc_block not in kn


def test_shared_prefix_is_deterministic_between_calls():
    """A prompt rebuilt per request must still produce identical leading bytes."""
    knowledge = _knowledge()
    first = knowledge.get_system_prompt()
    second = knowledge.get_system_prompt()
    assert first == second
    assert knowledge.get_knowledge_prompt() == knowledge.get_knowledge_prompt()


def test_prompts_keep_their_distinct_instructions():
    """Reordering must not leak one path's instructions into the other."""
    knowledge = _knowledge()
    diag = knowledge.get_system_prompt()
    kn = knowledge.get_knowledge_prompt()

    # Diagnostic-only trust protocol.
    assert "[VALIDATION TRUST STATUS]" in diag
    assert "[VALIDATION TRUST STATUS]" not in kn
    # Knowledge-only documentation framing.
    assert "[RELEVANT DOCUMENTATION]" in kn
    assert "[RELEVANT DOCUMENTATION]" not in diag
    # Both still ask for a concise, scoped answer.
    assert "Be concise" in diag
    assert "Be concise" in kn
