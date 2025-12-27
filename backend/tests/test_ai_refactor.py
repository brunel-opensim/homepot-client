"""Tests for AI Refactoring: DeviceResolver, PromptManager, and ContextBuilder updates."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add the workspace root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.context_builder import ContextBuilder  # noqa: E402
from ai.device_resolver import DeviceResolver  # noqa: E402
from ai.prompts import PromptManager  # noqa: E402

from homepot.models import AuditLog, HealthCheck  # noqa: E402


@pytest.mark.asyncio
async def test_device_resolver_cache_hit():
    """Test that DeviceResolver returns cached ID without DB query."""
    mock_session = AsyncMock()
    resolver = DeviceResolver(mock_session)

    # Pre-populate cache
    resolver._cache["uuid-123"] = 10

    result = await resolver.resolve("uuid-123")

    assert result == 10
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_device_resolver_db_hit():
    """Test that DeviceResolver queries DB on cache miss."""
    mock_session = AsyncMock()
    resolver = DeviceResolver(mock_session)

    # Mock DB result
    # scalar_one_or_none returns the integer ID directly because we select(Device.id)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 20
    mock_session.execute.return_value = mock_result

    result = await resolver.resolve("uuid-456")

    assert result == 20
    assert resolver._cache["uuid-456"] == 20
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_device_resolver_not_found():
    """Test that DeviceResolver returns None if device not found."""
    mock_session = AsyncMock()
    resolver = DeviceResolver(mock_session)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await resolver.resolve("uuid-999")

    assert result is None
    assert "uuid-999" not in resolver._cache


def test_prompt_manager_build_live_context():
    """Test PromptManager.build_live_context formatting."""
    context_data = {"error": "Error 1", "config": "Config A", "audit": "Audit B"}
    prediction = {"risk_level": "HIGH", "failure_probability": 0.8}
    risk_factors = ["Factor 1"]
    recent_events = ["Event 1"]

    prompt = PromptManager.build_live_context(
        device_id="dev-1",
        prediction=prediction,
        risk_factors=risk_factors,
        recent_events=recent_events,
        context_data=context_data,
    )

    assert "Device ID: dev-1" in prompt
    assert "Risk Level: HIGH" in prompt
    assert "Error 1" in prompt
    assert "Config A" in prompt
    assert "Audit B" in prompt


def test_prompt_manager_build_full_prompt():
    """Test PromptManager.build_full_prompt assembly."""
    live_ctx = "Live Context"
    long_term_ctx = "Long Term Context"
    short_term_ctx = "Short Term Context"

    full_prompt = PromptManager.build_full_prompt(
        live_ctx, long_term_ctx, short_term_ctx
    )

    assert "Live Context" in full_prompt
    assert "Relevant History:\nLong Term Context" in full_prompt
    assert "Current Conversation:\nShort Term Context" in full_prompt


@pytest.mark.asyncio
async def test_context_builder_uses_int_id_for_audit():
    """Test that ContextBuilder uses device_int_id for AuditLog query if provided."""
    mock_session = AsyncMock()

    # Mock result
    mock_audit = AuditLog(event_type="login", description="success")
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_audit]
    mock_session.execute.return_value = mock_result

    await ContextBuilder.get_audit_context(
        "uuid-123", session=mock_session, device_int_id=55
    )

    # Verify execution
    mock_session.execute.assert_called()


@pytest.mark.asyncio
async def test_context_builder_uses_int_id_for_health():
    """Test that ContextBuilder uses device_int_id for HealthCheck query if provided."""
    mock_session = AsyncMock()

    # Mock result
    mock_health = HealthCheck(is_healthy=True, status_code=200)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_health]
    mock_session.execute.return_value = mock_result

    # Testing get_metadata_context which uses get_health_context logic internally
    await ContextBuilder.get_metadata_context(
        "uuid-123", session=mock_session, device_int_id=55
    )

    # Verify execution
    mock_session.execute.assert_called()
