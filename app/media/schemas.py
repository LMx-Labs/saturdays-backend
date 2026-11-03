import uuid

from pydantic import BaseModel, Field


class MediaUploadResponse(BaseModel):
    id: uuid.UUID
    path: str = Field(
        ...,
        description=(
            "API path of the image, e.g. /api/v1/media/<id>. Prefix it with the "
            "API host to get the URL to store in logo_url, banner_url or image_url."
        ),
    )
    content_type: str
    size_bytes: int
