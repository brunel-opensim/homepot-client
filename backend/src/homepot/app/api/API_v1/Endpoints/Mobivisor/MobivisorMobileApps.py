"""API endpoints for managing Mobivisor Mobile Apps in the HomePot system.

This module provides proxy endpoints to interact with Mobivisor's mobile apps
API. Requests are forwarded to the Mobivisor API with proper authentication,
validation, and error handling.
"""

import logging
from typing import Any, Dict, List, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from homepot.app.utils.mobivisor_request import (
    _handle_mobivisor_response as handle_mobivisor_response,
)
from homepot.app.utils.mobivisor_request import (
    _make_mobivisor_request as make_mobivisor_request,
)
from homepot.config import get_mobivisor_api_config

logger = logging.getLogger(__name__)

router = APIRouter()


class ManagementFlags(BaseModel):
    """Represents Mobivisor application management flags."""

    removeAppOnMDMRemoval: bool


class MobivisorMobileAppPayload(BaseModel):
    """Payload model for updating a Mobivisor mobile app.

    This model mirrors the expected Mobivisor payload for
    `PUT /mobileapps/{application_id}`.

    Notes:
        - The upstream payload includes JSON keys like `_id` and `__v`.
          These are represented via field aliases.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id", min_length=1)
    appName: str = Field(..., min_length=1)
    appSize: int
    fileOrStore: str = Field(..., min_length=1)
    environment: str = Field(..., min_length=1)
    image_url: str = Field(..., min_length=1)
    appPackageName: str = Field(..., min_length=1)
    versionCode: str = Field(..., min_length=1)
    versionName: str = Field(..., min_length=1)
    silentInstallAfterSignin: bool
    autoInstall: bool
    localFilePath: str = Field(..., min_length=1)
    managedConfig: List[Dict[str, Any]] = Field(default_factory=list)
    v: int = Field(..., alias="__v")
    managementFlags: ManagementFlags
    createdAtStamp: int
    createdAt: str = Field(..., min_length=1)
    environmentEnhanced: str = Field(..., min_length=1)
    isChecked: bool
    description: str = Field(..., min_length=1)


class MobivisorMobileAppUpdateRequest(BaseModel):
    """Wrapper request body for updating a Mobivisor mobile app.

    Some clients send the payload nested under an `app` key:
    `{ "app": { ...mobile app fields... } }`.

    This model supports that request shape.
    """

    app: MobivisorMobileAppPayload


@router.put("/mobileapps/{application_id}", tags=["Mobivisor Mobile Apps"])
async def update_mobile_app(
    application_id: str,
    payload: Union[MobivisorMobileAppPayload, MobivisorMobileAppUpdateRequest],
) -> Dict[str, Any]:
    """Update a Mobivisor mobile app by application id.

    This endpoint proxies Mobivisor's `PUT /mobileapps/{application_id}` API.

    Args:
        application_id: The unique identifier of the application (required).
        payload: Request payload for the mobile app update. Accepts either a flat
            payload (mobile app fields at the root) or a wrapped payload under
            `app`.

    Returns:
        Dict[str, Any]: Proxied JSON response from Mobivisor API.

    Raises:
        HTTPException:
            - 400: if `application_id` is missing/blank.
            - 422: if request payload validation fails.
            - 500: if Mobivisor API URL/token is not configured.
            - 401/403/404/502: mapped upstream errors.
            - 504: timeout contacting Mobivisor.

    Example:
        ```python
        PUT /api/v1/mobivisor/mobileapps/689c7d4e40257462671afcfc
        ```
    """
    if not application_id or not application_id.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Validation Error",
                "message": "application_id is required",
            },
        )

    logger.info("Updating Mobivisor mobile app: %s", application_id)

    # Forward in the same shape the client sent (some Mobivisor deployments
    # expect `{ "app": { ... } }`, while others accept a flat payload).
    upstream_payload = payload.model_dump(by_alias=True)
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request(
        "PUT",
        f"mobileapps/{application_id}",
        config=config,
        json=upstream_payload,
    )
    return handle_mobivisor_response(response, f"update mobile app {application_id}")
