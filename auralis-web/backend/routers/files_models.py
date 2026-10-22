"""
Files router response bodies (split from files.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pydantic import BaseModel, Field
from typing import Literal


class UploadResultItem(BaseModel):
    """Per-file outcome of an upload batch.

    The success and failure branches emit different key sets — only
    `filename`, `status` and `message` are common — so the track fields are
    optional rather than required.
    """
    filename: str = Field(description="Client-supplied file name")
    status: Literal["success", "error"] = Field(description="Per-file outcome")
    message: str = Field(description="Human-readable detail")
    track_id: int | None = Field(default=None, description="Created track ID, on success")
    title: str | None = Field(default=None, description="Derived track title, on success")
    duration: float | None = Field(default=None, description="Duration in seconds, on success")
    sample_rate: int | None = Field(default=None, description="Sample rate in Hz, on success")


class UploadResultResponse(BaseModel):
    """Result of an audio file upload batch.

    Partial success is normal: the route returns 200 with a mix of
    `status: "success"` and `status: "error"` entries rather than failing the
    whole batch.
    """
    results: list[UploadResultItem] = Field(
        default_factory=list,
        description="One entry per uploaded file, in request order",
    )


class SupportedFormatsResponse(BaseModel):
    """Audio formats, sample rates, and bit depths the backend accepts."""
    input_formats: list[str] = Field(description="Accepted input file extensions")
    output_formats: list[str] = Field(description="Available output file extensions")
    sample_rates: list[int] = Field(description="Supported sample rates in Hz")
    bit_depths: list[int] = Field(description="Supported bit depths")
