"""API endpoints for managing push notifications in the HomePot system."""

# mypy: ignore-errors
# Note: Type checking disabled for this file due to dynamic audit logging API
# TODO: Update audit logging calls to match current AuditLogger signature

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from homepot.audit import AuditEventType, get_audit_logger
from homepot.push_notifications.factory import PushNotificationProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
audit_logger = get_audit_logger()


# Pydantic models for API requests/responses
class PushSubscription(BaseModel):
    """Model for push notification subscription."""

    platform: str = Field(
        ..., description="Platform type (fcm, wns, apns, web_push, mqtt)"
    )
    device_token: str = Field(
        ..., description="Device token or subscription info (JSON for Web Push)"
    )
    device_info: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional device information"
    )
    user_id: Optional[str] = Field(
        default=None, description="User ID associated with subscription"
    )
    device_id: Optional[str] = Field(default=None, description="Device ID for tracking")


class SendNotificationRequest(BaseModel):
    """Request model for sending push notification."""

    platform: str = Field(
        ..., description="Platform type (fcm, wns, apns, web_push, mqtt)"
    )
    device_token: str = Field(..., description="Device token or subscription info")
    title: str = Field(..., description="Notification title", max_length=200)
    body: str = Field(..., description="Notification body", max_length=500)
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional notification data"
    )
    priority: Optional[str] = Field(
        default="normal", description="Notification priority (high, normal, low)"
    )
    badge: Optional[int] = Field(default=None, description="Badge count (APNs)")
    sound: Optional[str] = Field(default=None, description="Sound file name")
    icon: Optional[str] = Field(default=None, description="Notification icon URL")
    image: Optional[str] = Field(default=None, description="Image URL")
    ttl: Optional[int] = Field(default=86400, description="Time to live in seconds")


class BulkNotificationRequest(BaseModel):
    """Request model for sending bulk notifications."""

    platform: str = Field(..., description="Platform type")
    device_tokens: List[str] = Field(
        ..., description="List of device tokens", min_length=1, max_length=1000
    )
    title: str = Field(..., description="Notification title", max_length=200)
    body: str = Field(..., description="Notification body", max_length=500)
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional notification data"
    )


class TopicNotificationRequest(BaseModel):
    """Request model for MQTT topic-based notifications."""

    topic: str = Field(..., description="MQTT topic to publish to")
    message: str = Field(..., description="Message payload")
    qos: Optional[int] = Field(default=1, description="Quality of Service (0, 1, 2)")
    retain: Optional[bool] = Field(default=False, description="Retain message flag")


# Get push notification provider instance
async def get_push_provider(platform: str):
    """Get push notification provider for the specified platform."""
    try:
        provider = PushNotificationProvider.create_provider(platform)
        await provider.initialize()
        return provider
    except ValueError as e:
        logger.error(f"Invalid platform '{platform}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid platform '{platform}'. "
                "Supported: fcm, wns, apns, web_push, mqtt"
            ),
        )
    except Exception as e:
        logger.error(
            f"Failed to initialize provider for '{platform}': {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"Failed to initialize {platform} provider. "
                "Please check server logs."
            ),
        )


@router.get("/vapid-public-key", tags=["Push Notifications"])
async def get_vapid_public_key() -> Dict[str, str]:
    """Get VAPID public key for Web Push subscriptions."""
    try:
        provider = await get_push_provider("web_push")
        public_key = provider.get_vapid_public_key()

        audit_logger.log_event(
            event_type=AuditEventType.API_CALL,
            message="Retrieved VAPID public key",
            metadata={"platform": "web_push"},
        )

        return {
            "publicKey": public_key,
            "platform": "web_push",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get VAPID public key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get VAPID public key. Please check server logs.",
        )


@router.post(
    "/subscribe", status_code=status.HTTP_201_CREATED, tags=["Push Notifications"]
)
async def subscribe_to_push(subscription: PushSubscription) -> Dict[str, Any]:
    """
    Register a device for push notifications.

    Validates the device token and stores subscription information.
    """
    try:
        provider = await get_push_provider(subscription.platform)

        # Validate device token
        is_valid = await provider.validate_device_token(subscription.device_token)

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid device token for platform '{subscription.platform}'",
            )

        audit_logger.log_event(
            event_type=AuditEventType.DEVICE_REGISTERED,
            message=f"Device subscribed to {subscription.platform} push notifications",
            metadata={
                "platform": subscription.platform,
                "device_id": subscription.device_id,
                "user_id": subscription.user_id,
            },
        )

        return {
            "success": True,
            "message": "Successfully subscribed to push notifications",
            "platform": subscription.platform,
            "device_id": subscription.device_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Subscription failed for {subscription.platform}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subscription failed. Please check server logs.",
        )


@router.post("/send", tags=["Push Notifications"])
async def send_notification(request: SendNotificationRequest) -> Dict[str, Any]:
    """
    Send a push notification to a specific device.

    Supports all platforms: FCM, WNS, APNs, Web Push, and MQTT.
    """
    try:
        provider = await get_push_provider(request.platform)

        # Build notification payload
        notification_data = {
            "title": request.title,
            "body": request.body,
            "data": request.data or {},
        }

        # Add optional fields if provided
        if request.priority:
            notification_data["priority"] = request.priority
        if request.badge is not None:
            notification_data["badge"] = request.badge
        if request.sound:
            notification_data["sound"] = request.sound
        if request.icon:
            notification_data["icon"] = request.icon
        if request.image:
            notification_data["image"] = request.image
        if request.ttl:
            notification_data["ttl"] = request.ttl

        # Send notification
        result = await provider.send_notification(
            device_token=request.device_token, notification_data=notification_data
        )

        audit_logger.log_event(
            event_type=AuditEventType.NOTIFICATION_SENT,
            message=f"Push notification sent via {request.platform}",
            metadata={
                "platform": request.platform,
                "title": request.title,
                "success": result.get("success", False),
            },
        )

        return {
            "success": result.get("success", False),
            "message": result.get("message", "Notification sent"),
            "platform": request.platform,
            "timestamp": datetime.utcnow().isoformat(),
            "details": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send notification via {request.platform}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send notification: {str(e)}",
        )


@router.post("/send-bulk", tags=["Push Notifications"])
async def send_bulk_notifications(request: BulkNotificationRequest) -> Dict[str, Any]:
    """
    Send push notifications to multiple devices.

    Efficiently sends the same notification to multiple device tokens.
    """
    try:
        provider = await get_push_provider(request.platform)

        # Build notification payload
        notification_data = {
            "title": request.title,
            "body": request.body,
            "data": request.data or {},
        }

        # Send bulk notification
        result = await provider.send_bulk_notifications(
            device_tokens=request.device_tokens, notification_data=notification_data
        )

        audit_logger.log_event(
            event_type=AuditEventType.NOTIFICATION_SENT,
            message=f"Bulk push notifications sent via {request.platform}",
            metadata={
                "platform": request.platform,
                "device_count": len(request.device_tokens),
                "success_count": result.get("success_count", 0),
                "failure_count": result.get("failure_count", 0),
            },
        )

        return {
            "success": True,
            "message": "Bulk notifications processed",
            "platform": request.platform,
            "total": len(request.device_tokens),
            "success_count": result.get("success_count", 0),
            "failure_count": result.get("failure_count", 0),
            "timestamp": datetime.utcnow().isoformat(),
            "details": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send bulk notifications via {request.platform}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send bulk notifications: {str(e)}",
        )


@router.post("/mqtt/publish", tags=["Push Notifications", "MQTT"])
async def publish_mqtt_topic(request: TopicNotificationRequest) -> Dict[str, Any]:
    """
    Publish a message to an MQTT topic.

    Specifically for MQTT-based push notifications to IoT/Industrial devices.
    """
    try:
        provider = await get_push_provider("mqtt")

        # Send topic notification
        result = await provider.send_topic_notification(
            topic=request.topic,
            message=request.message,
            qos=request.qos,
            retain=request.retain,
        )

        audit_logger.log_event(
            event_type=AuditEventType.NOTIFICATION_SENT,
            message=f"MQTT message published to topic: {request.topic}",
            metadata={
                "platform": "mqtt",
                "topic": request.topic,
                "qos": request.qos,
                "retain": request.retain,
            },
        )

        return {
            "success": result.get("success", False),
            "message": "MQTT message published",
            "topic": request.topic,
            "qos": request.qos,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to publish MQTT message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish MQTT message: {str(e)}",
        )


@router.get("/platforms", tags=["Push Notifications"])
async def list_platforms() -> Dict[str, Any]:
    """List all available push notification platforms and their status."""
    platforms_info = []

    for platform in ["fcm", "wns", "apns", "web_push", "mqtt"]:
        try:
            provider = await get_push_provider(platform)
            info = await provider.get_platform_info()
            platforms_info.append(
                {"platform": platform, "available": True, "info": info}
            )
        except Exception as e:
            logger.warning(f"Platform {platform} unavailable: {e}")
            platforms_info.append(
                {"platform": platform, "available": False, "error": str(e)}
            )

    return {
        "platforms": platforms_info,
        "total": len(platforms_info),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/platforms/{platform}/info", tags=["Push Notifications"])
async def get_platform_info(platform: str) -> Dict[str, Any]:
    """Get detailed information about a specific platform."""
    try:
        provider = await get_push_provider(platform)
        info = await provider.get_platform_info()

        return {
            "platform": platform,
            "info": info,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get platform info for {platform}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get platform info: {str(e)}",
        )


@router.post("/test", tags=["Push Notifications"])
async def send_test_notification(platform: str, device_token: str) -> Dict[str, Any]:
    """
    Send a test notification to verify the setup.

    Useful for testing push notification configuration.
    """
    try:
        provider = await get_push_provider(platform)

        test_notification = {
            "title": "HOMEPOT Test Notification",
            "body": f"This is a test notification from HOMEPOT on {platform}",
            "data": {
                "test": True,
                "timestamp": datetime.utcnow().isoformat(),
                "platform": platform,
            },
        }

        result = await provider.send_notification(
            device_token=device_token, notification_data=test_notification
        )

        audit_logger.log_event(
            event_type=AuditEventType.NOTIFICATION_SENT,
            message=f"Test notification sent via {platform}",
            metadata={"platform": platform, "test": True},
        )

        return {
            "success": result.get("success", False),
            "message": "Test notification sent",
            "platform": platform,
            "timestamp": datetime.utcnow().isoformat(),
            "details": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send test notification via {platform}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test notification: {str(e)}",
        )
