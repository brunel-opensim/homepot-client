"""API endpoint for device support-bundle upload and retrieval.

Devices upload a support bundle (zip) produced by the
``collect_support_bundle`` command. Technicians/admins can then download
the bundle from the web UI.

Devices authenticate via ``X-Device-ID`` / ``X-API-Key``. Downloads are
gated behind the Manage (``root_access``) permission via the standard
user auth dependency.
"""

import logging
import os
from typing import Any, Dict
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from homepot.app.auth_utils import get_current_device, get_current_user, require_user
from homepot.models import Device, User

logger = logging.getLogger(__name__)
router = APIRouter()

# Directory where uploaded support bundles are stored.
_BUNDLE_DIR = os.path.join(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    ),
    "data",
    "support-bundles",
)


def _ensure_bundle_dir() -> str:
    os.makedirs(_BUNDLE_DIR, exist_ok=True)
    return _BUNDLE_DIR


@router.post(
    "/devices/{device_id}/support-bundle",
    tags=["Agent"],
    dependencies=[Depends(get_current_device)],
)
async def upload_support_bundle(
    device_id: str,
    file: UploadFile = File(...),
    command_id: str = Form(None),
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Upload a support bundle zip from a device.

    The device must be the authenticated device (``X-Device-ID`` /
    ``X-API-Key``). The file is stored server-side and a download URL is
    returned.
    """
    if current_device.device_id != device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device can only upload its own support bundle",
        )

    _ensure_bundle_dir()

    # Validate device_id does not contain path traversal sequences.
    if not device_id or ".." in device_id or "/" in device_id or "\\\\" in device_id:
        raise HTTPException(status_code=400, detail="Invalid device_id")

    # Use only the server-generated UUID for the filename so no
    # user-provided value flows into the filesystem path (CodeQL).
    bundle_id = str(uuid.uuid4())
    filename = f"{bundle_id}.zip"
    filepath = os.path.join(_BUNDLE_DIR, filename)

    try:
        contents = await file.read()
        with open(filepath, "wb") as fh:
            fh.write(contents)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to store support bundle for %s", device_id)
        raise HTTPException(status_code=500, detail=f"Failed to store bundle: {exc}")

    logger.info(
        "Support bundle uploaded: device=%s bundle_id=%s size=%d",
        device_id,
        bundle_id,
        len(contents),
    )

    return {
        "status": "success",
        "bundle_id": bundle_id,
        "filename": filename,
        "download_url": f"/api/v1/support-bundles/{bundle_id}",
        "size_bytes": len(contents),
    }


@router.get(
    "/support-bundles/{bundle_id}",
    tags=["Support Bundles"],
    dependencies=[Depends(require_user())],
)
async def download_support_bundle(
    bundle_id: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Download a previously uploaded support bundle (user-authenticated)."""
    _ensure_bundle_dir()

    # Validate bundle_id is a UUID to prevent path traversal.
    try:
        uuid.UUID(bundle_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bundle_id")

    # Validate bundle_id is a UUID.
    try:
        uuid.UUID(bundle_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bundle_id")

    # Read file content into memory to avoid passing user-derived path
    # to FileResponse (satisfies CodeQL path-injection check).
    filename = f"{bundle_id}.zip"
    filepath = os.path.join(_BUNDLE_DIR, filename)

    # Containment check: resolved path must stay within bundle dir.
    real_filepath = os.path.realpath(filepath)
    real_bundle_dir = os.path.realpath(_BUNDLE_DIR)
    if not real_filepath.startswith(real_bundle_dir + os.sep):
        raise HTTPException(status_code=400, detail="Invalid bundle path")

    if not os.path.isfile(real_filepath):
        raise HTTPException(status_code=404, detail="Support bundle not found")

    with open(real_filepath, "rb") as fh:
        content = fh.read()

    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
