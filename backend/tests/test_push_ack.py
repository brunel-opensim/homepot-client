"""Tests for push notification acknowledgment endpoint."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest


@pytest.mark.asyncio
async def test_acknowledge_push_notification(async_client, mocker):
    """Test successful acknowledgment of a push notification."""
    # Mock session
    mock_session = AsyncMock()

    # Mock database result
    mock_result = MagicMock()
    mock_log_entry = MagicMock()
    mock_log_entry.sent_at = datetime.utcnow()
    mock_log_entry.received_at = None
    mock_result.scalar_one_or_none.return_value = mock_log_entry
    mock_session.execute.return_value = mock_result

    # Mock database service
    mock_db_service = MagicMock()

    # Configure get_session as async context manager
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_db_service.get_session.return_value = mock_ctx

    # Mock get_database_service
    mocker.patch(
        "homepot.app.api.API_v1.Endpoints.PushNotificationEndpoint.get_database_service",
        new_callable=AsyncMock,
        return_value=mock_db_service,
    )

    # Send ACK request
    message_id = str(uuid.uuid4())
    ack_data = {
        "message_id": message_id,
        "device_id": "test-device-123",
        "status": "delivered",
        "received_at": datetime.utcnow().isoformat(),
        "platform": "fcm",
    }

    response = await async_client.post("/api/v1/push/ack", json=ack_data)

    # Verify response
    assert response.status_code == 200
    assert response.json() == {"status": "acknowledged"}

    # Verify database interactions
    assert mock_session.execute.called
    assert mock_log_entry.status == "delivered"
    assert mock_log_entry.received_at is not None
    assert mock_log_entry.latency_ms is not None
    mock_session.add.assert_called_with(mock_log_entry)
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_acknowledge_push_notification_unknown_id(async_client, mocker):
    """Test acknowledgment with an unknown message ID."""
    # Mock session
    mock_session = AsyncMock()

    # Mock database result (None found)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # Mock database service
    mock_db_service = MagicMock()

    # Configure get_session as async context manager
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_db_service.get_session.return_value = mock_ctx

    # Mock get_database_service
    mocker.patch(
        "homepot.app.api.API_v1.Endpoints.PushNotificationEndpoint.get_database_service",
        new_callable=AsyncMock,
        return_value=mock_db_service,
    )

    # Send ACK request
    ack_data = {
        "message_id": "unknown-id",
        "device_id": "test-device-123",
        "status": "delivered",
        "received_at": datetime.utcnow().isoformat(),
        "platform": "fcm",
    }

    response = await async_client.post("/api/v1/push/ack", json=ack_data)

    assert response.status_code == 200
    assert response.json() == {"status": "acknowledged"}
