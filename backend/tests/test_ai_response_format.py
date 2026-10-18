"""Tests for AI answer-format cleanup (``_strip_answer_markup``).

The AI context is built from bracketed blocks ([RELEVANT DOCUMENTATION],
[RELEVANT MEMORIES], ...), and the small model sometimes mimics that style by
wrapping its reply in a leading ``[ANSWER]`` tag or appending a trailing
``Source: ...`` line. ``AIEndpoint._strip_answer_markup`` removes those
artifacts so internal markup never reaches the user; the cited files are
returned separately in the response's ``sources`` field.
"""

import os
import sys

# Add the workspace root to sys.path so the `ai` package resolves in tests.
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from homepot.app.api.API_v1.Endpoints.AIEndpoint import (  # noqa: E402
    _strip_answer_markup,
)


def test_removes_leading_answer_tag():
    """A leading [ANSWER] tag (and stacked/colon variants) is removed."""
    assert _strip_answer_markup("[ANSWER]\nTo enrol a device, go to Devices.") == (
        "To enrol a device, go to Devices."
    )
    assert _strip_answer_markup("[ANSWER]: The fleet is healthy.") == (
        "The fleet is healthy."
    )
    assert _strip_answer_markup("[ANSWER]\n[ANSWER]  Two tags.") == "Two tags."


def test_removes_trailing_source_line():
    """A trailing 'Source:'/'Sources:' line is dropped (sources are separate)."""
    text = "Register the device in the dashboard.\nSource: [RELEVANT DOCUMENTATION]"
    assert _strip_answer_markup(text) == "Register the device in the dashboard."

    # Trailing blank lines after the source line are dropped too.
    text2 = "Answer here.\nSources: docs/device-registration.md\n\n"
    assert _strip_answer_markup(text2) == "Answer here."


def test_preserves_plain_answer():
    """Plain answers, empty strings, and inline doc references are untouched."""
    assert _strip_answer_markup("The fleet is healthy.") == "The fleet is healthy."
    assert _strip_answer_markup("") == ""
    # A mid-sentence file reference is legitimate content and must stay.
    inline = "See docs/device-registration.md for the full workflow."
    assert _strip_answer_markup(inline) == inline


def test_strips_tag_and_source_together():
    """Both artifacts on one response are removed, leaving the body intact."""
    text = "[ANSWER]\nUse the Register New Device flow.\nSource: docs/device-registration.md"
    assert _strip_answer_markup(text) == "Use the Register New Device flow."
