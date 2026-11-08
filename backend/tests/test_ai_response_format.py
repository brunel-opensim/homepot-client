"""Tests for AI answer-format cleanup and action-claim detection.

The AI context is built from bracketed blocks ([RELEVANT DOCUMENTATION],
[RELEVANT MEMORIES], ...), and the small model sometimes mimics that style by
wrapping its reply in a leading ``[ANSWER]`` tag or appending a trailing
``Source: ...`` line. ``AIEndpoint._strip_answer_markup`` removes those
artifacts so internal markup never reaches the user; the cited files are
returned separately in the response's ``sources`` field.

A chat turn can only record a proposal, never send a command.
``_claims_action_performed`` detects a model that narrates an action as
already done so the endpoint can prepend a truthful correction.
"""

import os
import sys

# Add the workspace root to sys.path so the `ai` package resolves in tests.
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from homepot.app.api.API_v1.Endpoints.AIEndpoint import (  # noqa: E402
    _annotate_action_claims,
    _claims_action_performed,
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


def test_detects_issued_sent_and_status_claims():
    """Past-tense verbs and status lines that imply a command already ran."""
    claims = [
        "## Health Check Command Issued",
        "**Status:** SENT \u2713",
        "Status: sent",
        "The command has been sent.",
        "The health check was executed on the device.",
        "Command sent successfully.",
        "I have issued the dispatch.",
        "Issued by: maziar (Admin)",
    ]
    for text in claims:
        assert _claims_action_performed(text) is True, text


def test_ignores_negated_and_future_tense_statements():
    """Denials and future/proposed wording must not be flagged as claims."""
    safe = [
        "",
        "No command has been sent.",
        "No command sent.",
        "The command was not sent.",
        "Status: pending approval.",
        "This will propose a health check; nothing runs until approval.",
        "The health check will be sent once a technician approves it.",
        "Proposal recorded and awaiting review.",
    ]
    for text in safe:
        assert _claims_action_performed(text) is False, text


def test_annotates_claim_without_proposal_as_advisory():
    """A claim with no persisted proposal gets the advisory correction."""
    text = "## Health Check Command Issued\n**Status:** SENT"
    corrected = _annotate_action_claims(text, proposal_created=False)
    assert corrected.startswith("> **No command was issued.**")
    assert "advisory only" in corrected
    assert corrected.endswith(text)


def test_annotates_claim_with_proposal_as_recorded():
    """A claim with a persisted proposal points the reader to AI Proposals."""
    text = "The command has been sent to the device."
    corrected = _annotate_action_claims(text, proposal_created=True)
    assert corrected.startswith("> **No command was issued.**")
    assert "proposal was recorded" in corrected
    assert corrected.endswith(text)


def test_leaves_safe_answers_untouched():
    """Answers that do not claim an action are returned byte-for-byte."""
    text = "The device is healthy. A proposal is pending approval."
    assert _annotate_action_claims(text, proposal_created=True) == text
    assert _annotate_action_claims(text, proposal_created=False) == text
