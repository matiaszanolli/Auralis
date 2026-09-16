"""
Processing Router Models

Request and response bodies for the /api/processing endpoints (#5472). Split
out of routers/processing_api.py, which re-exports every name here.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from core.processing_engine import ProcessingStatus


class ProcessingSettings(BaseModel):
    """Processing settings from UI"""
    # Literal, not a bare str (#4735): _build_config dispatches on this with an
    # if/elif chain that has no else, so an unrecognised value silently skipped
    # set_processing_mode() entirely and ran adaptive under whatever mode the
    # config defaulted to. Now a 422 at the route boundary.
    mode: Literal["adaptive", "reference", "hybrid"] = "adaptive"
    # Literal, not a bare str (#4746): output_format is interpolated straight
    # into the output filename extension, and bit_depth is mapped through a
    # subtype table (core/processing_engine.py) with a silent PCM_16
    # fallback for anything unrecognised — a bad value used to reach
    # libsndfile and fail deep inside the save step as a generic job
    # failure, not a 422 at submit time.
    output_format: Literal["wav", "flac", "mp3"] = "wav"
    bit_depth: Literal[16, 24, 32] = 16
    sample_rate: int | None = None  # None = keep original

    # EQ settings
    eq: dict[str, Any] | None = None

    # Dynamics settings
    dynamics: dict[str, Any] | None = None

    # Level matching settings
    level_matching: dict[str, Any] | None = None

    # Genre override
    genre_override: str | None = None

    @property
    def requires_reference(self) -> bool:
        """True for the modes whose whole point is matching a reference.

        A job in one of these modes with no reference is rejected at submit
        time (#4735 for reference, #5058 for hybrid), rather than degrading to
        adaptive-mastered audio labelled as a reference/hybrid job.
        """
        return self.mode in ("reference", "hybrid")

    @model_validator(mode="after")
    def _validate_format_bit_depth_combo(self) -> ProcessingSettings:
        """Reject (output_format, bit_depth) pairs libsndfile cannot
        actually write, rather than letting them fail deep inside the save
        step (core/processing_engine.py's subtype_map) as a generic,
        misleading job failure (#4746).

        Verified against the installed libsndfile (soundfile.available_subtypes):
        - WAV:  PCM_16 / PCM_24 / PCM_32 all valid.
        - FLAC: PCM_16 / PCM_24 valid; FLAC has no 32-bit PCM subtype.
        - MP3:  only MPEG_LAYER_I/II/III subtypes exist — none of the PCM_*
          subtypes bit_depth maps to are valid for MP3, so no (mp3, bit_depth)
          combination can currently succeed via this pipeline.
        """
        if self.output_format == "mp3":
            raise ValueError(
                "output_format='mp3' is not currently supported — MP3 is a "
                "lossy format with no PCM bit depth, and the save pipeline "
                "only writes PCM subtypes. Use 'wav' or 'flac'."
            )
        if self.output_format == "flac" and self.bit_depth == 32:
            raise ValueError(
                "output_format='flac' does not support bit_depth=32 "
                "(FLAC's maximum is 24-bit PCM). Use bit_depth=16 or 24, "
                "or output_format='wav' for 32-bit."
            )
        return self


class ProcessRequest(BaseModel):
    """Request to process audio"""
    input_path: str
    settings: ProcessingSettings
    reference_path: str | None = None


class ProcessResponse(BaseModel):
    """Response after submitting processing job"""
    job_id: str
    # ProcessingStatus, not bare str (#3896): the enum is the authority on the
    # value set and, being a str Enum, serialises to the same JSON while making
    # OpenAPI publish the five valid values instead of an opaque "string".
    status: ProcessingStatus
    message: str


class JobStatusResponse(BaseModel):
    """Job status response"""
    job_id: str
    status: ProcessingStatus
    progress: float
    error_message: str | None = None
    result_data: dict[str, Any] | None = None


class CancelJobResponse(BaseModel):
    """Response after cancelling a job"""
    message: str
    job_id: str


class JobListResponse(BaseModel):
    """Response listing processing jobs"""
    jobs: list[JobStatusResponse]
    total: int


class QueueStatusResponse(BaseModel):
    """Current processing queue status"""
    queued: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    total: int = 0

    model_config = {"extra": "allow"}


class PresetsResponse(BaseModel):
    """Available processing presets"""
    presets: dict[str, Any]


class ProcessingParametersResponse(BaseModel):
    """Live auto-mastering parameters from the continuous-space system.

    `is_default` distinguishes "no measurement yet" from real measurements
    that happen to land on the default values (#3779) — both branches return
    200 with the same field set.
    """
    is_default: bool = Field(description="True when these are placeholders, not measurements")
    spectral_balance: float = Field(description="Spectral-balance coordinate (0–1)")
    dynamic_range: float = Field(description="Dynamic-range coordinate (0–1)")
    energy_level: float = Field(description="Energy-level coordinate (0–1)")
    target_lufs: float = Field(description="Target integrated loudness (LUFS)")
    peak_target_db: float = Field(description="Target true peak (dBFS)")
    bass_boost: float = Field(description="Low-shelf gain (dB)")
    air_boost: float = Field(description="High-shelf gain (dB)")
    compression_amount: float = Field(description="Compression amount (0–1)")
    expansion_amount: float = Field(description="Expansion amount (0–1)")
    stereo_width: float = Field(description="Target stereo width")


class CleanupResponse(BaseModel):
    """Response after cleaning up old jobs"""
    message: str
    removed: int
