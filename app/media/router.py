import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.core.config import settings
from app.core.database import get_db_session
from app.core.exceptions import AppException
from app.media.schemas import MediaUploadResponse
from app.media.service import MAX_UPLOAD_BYTES, MediaService

router = APIRouter(prefix="/media", tags=["Media"])

# Images never change once uploaded (the id is derived from their content), so
# browsers and Vercel's CDN may keep them for a year.
_IMMUTABLE = "public, max-age=31536000, s-maxage=31536000, immutable"


@router.post(
    "",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image",
    description=(
        "Send the image file itself as the request body (Content-Type image/png, "
        "image/jpeg or image/webp, up to 3 MB). Restaurant staff and admins only. "
        "Uploading identical bytes again returns the existing image."
    ),
)
async def upload_media(
    request: Request,
    current_user: UserClaims = Depends(
        require_role(["PlatformAdmin", "Admin", "MerchantOwner", "BranchManager"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> MediaUploadResponse:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES + 1024:
        raise AppException(
            message="Image is too large.",
            error_code="MEDIA_TOO_LARGE",
            status_code=413,
        )
    media_id, content_type, size = await MediaService(session).store(
        await request.body(), uuid.UUID(current_user.sub)
    )
    return MediaUploadResponse(
        id=media_id,
        path=f"{settings.API_V1_STR}/media/{media_id}",
        content_type=content_type,
        size_bytes=size,
    )


@router.get(
    "/{media_id}",
    response_class=Response,
    responses={200: {"content": {"image/png": {}, "image/jpeg": {}, "image/webp": {}}}},
    summary="Fetch an uploaded image",
    description="Public. Returns the image bytes with long-lived cache headers.",
)
async def get_media(
    media_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    content_type, digest, data = await MediaService(session).get(media_id)
    headers = {
        "Cache-Control": _IMMUTABLE,
        "ETag": f'"{digest}"',
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
    }
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(content=data, media_type=content_type, headers=headers)
