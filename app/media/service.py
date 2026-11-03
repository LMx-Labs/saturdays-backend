import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AppException,
    EntityNotFoundError,
    UnprocessableEntityError,
)
from app.media.models import MediaFile

# Larger than the admin app's resized images (about 1 MB) but under Vercel's
# 4.5 MB request-body limit.
MAX_UPLOAD_BYTES = 3 * 1024 * 1024


def sniff_image_type(data: bytes) -> str | None:
    """Content type from the file's own bytes; the client's claim is ignored.

    Only raster formats browsers display safely. SVG is refused on purpose: it
    can carry scripts.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class MediaService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def store(
        self, data: bytes, uploaded_by: uuid.UUID | None
    ) -> tuple[uuid.UUID, str, int]:
        """Save an image and return (id, content_type, size_bytes)."""
        if not data:
            raise UnprocessableEntityError(
                message="The upload is empty.", error_code="MEDIA_EMPTY"
            )
        if len(data) > MAX_UPLOAD_BYTES:
            raise AppException(
                message=f"Image is too large. The limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                error_code="MEDIA_TOO_LARGE",
                status_code=413,
            )
        content_type = sniff_image_type(data)
        if content_type is None:
            raise UnprocessableEntityError(
                message="Only PNG, JPEG or WebP images can be uploaded.",
                error_code="MEDIA_UNSUPPORTED_TYPE",
            )

        digest = hashlib.sha256(data).hexdigest()
        existing = await self._find_by_digest(digest)
        if existing:
            return existing

        media = MediaFile(
            sha256=digest,
            content_type=content_type,
            size_bytes=len(data),
            data=data,
            uploaded_by=uploaded_by,
        )
        self.session.add(media)
        try:
            await self.session.commit()
        except IntegrityError:
            # Someone uploaded the very same image at the same moment.
            await self.session.rollback()
            existing = await self._find_by_digest(digest)
            if existing is None:
                raise
            return existing
        return media.id, content_type, len(data)

    async def get(self, media_id: uuid.UUID) -> tuple[str, str, bytes]:
        """Return (content_type, sha256, bytes) or raise 404."""
        row = (
            await self.session.execute(
                select(MediaFile.content_type, MediaFile.sha256, MediaFile.data).where(
                    MediaFile.id == media_id
                )
            )
        ).first()
        if row is None:
            raise EntityNotFoundError(
                message="Image not found.", error_code="MEDIA_NOT_FOUND"
            )
        return row.content_type, row.sha256, row.data

    async def _find_by_digest(self, digest: str) -> tuple[uuid.UUID, str, int] | None:
        row = (
            await self.session.execute(
                select(
                    MediaFile.id, MediaFile.content_type, MediaFile.size_bytes
                ).where(MediaFile.sha256 == digest)
            )
        ).first()
        return (row.id, row.content_type, row.size_bytes) if row else None
