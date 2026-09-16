"""
System and Cache Schemas

Health/version and cache statistics response models. Split out of
schemas.py (#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from pydantic import BaseModel, Field

# ============================================================================
# System / Health Response Models
# ============================================================================

# Typed response models for /api/health and /api/version (fixes #3863 / BE-RH-18).

class HealthResponse(BaseModel):
    """Response model for GET /api/health."""
    status: str = Field(description="Liveness: always 'healthy' while the process serves requests")
    auralis_available: bool = Field(
        description="True only when the engine imported AND its library database "
                    "initialised; false after a failed or rolled-back startup (#4684)"
    )


class VersionInfoResponse(BaseModel):
    """Response model for GET /api/version (matches get_version_info() shape)."""
    version: str = Field(description="Full semantic version string (e.g. '1.2.1-beta.1')")
    major: int = Field(description="Major version number")
    minor: int = Field(description="Minor version number")
    patch: int = Field(description="Patch version number")
    prerelease: str = Field(default="", description="Pre-release identifier (empty for stable)")
    build: str = Field(default="", description="Build metadata (empty if not set)")
    build_date: str = Field(default="", description="Build date (ISO format)")
    git_commit: str = Field(default="", description="Git commit hash (empty if not set)")
    api_version: str = Field(default="v1", description="API version for compatibility")
    db_schema_version: int = Field(default=0, description="Database schema version")
    display: str = Field(description="User-friendly display version string")


# ============================================================================
# Cache Schemas (Phase B.2)
# ============================================================================

class TrackCacheStatusResponse(BaseModel):
    """Per-track cache status summary."""
    track_id: int = Field(description="Track identifier")
    total_chunks: int = Field(description="Total number of chunks for this track")
    cached_original: int = Field(description="Number of unprocessed chunks cached")
    cached_processed: int = Field(description="Number of processed chunks cached")
    completion_percent: float = Field(description="Overall cache completion percentage")
    fully_cached: bool = Field(description="Whether all chunks are cached")
    estimated_cache_time_seconds: float | None = Field(
        default=None,
        description="Estimated seconds until fully cached"
    )


class CacheTierStats(BaseModel):
    """Statistics for a single cache tier."""
    tier_name: str = Field(description="Tier identifier (e.g. 'tier1', 'tier2')")
    chunks: int = Field(description="Number of chunks stored in this tier")
    size_mb: float = Field(description="Total size of cached data in MB")
    hits: int = Field(description="Total cache hits")
    misses: int = Field(description="Total cache misses")
    hit_rate: float = Field(description="Cache hit rate (0–1)")


class OverallCacheStats(BaseModel):
    """Aggregate statistics across all cache tiers."""
    total_chunks: int = Field(description="Total chunks across all tiers")
    total_size_mb: float = Field(description="Total cached data size in MB")
    total_hits: int = Field(description="Total hits across all tiers")
    total_misses: int = Field(description="Total misses across all tiers")
    overall_hit_rate: float = Field(description="Combined hit rate (0–1)")
    tracks_cached: int = Field(description="Number of distinct tracks with cached data")


class CacheHealthResponse(BaseModel):
    """Cache subsystem health report."""
    healthy: bool = Field(description="Overall health indicator")
    tier1_size_mb: float = Field(description="Tier 1 (memory) size in MB")
    tier1_healthy: bool = Field(description="Tier 1 health indicator")
    tier2_size_mb: float = Field(description="Tier 2 (disk) size in MB")
    tier2_healthy: bool = Field(description="Tier 2 health indicator")
    total_size_mb: float = Field(description="Combined cache size in MB")
    memory_healthy: bool = Field(description="Memory pressure indicator")
    tier1_hit_rate: float = Field(description="Tier 1 hit rate (0–1)")
    overall_hit_rate: float = Field(description="Overall hit rate across all tiers (0–1)")


class CacheStatsResponse(BaseModel):
    """Full cache statistics response."""
    tier1: CacheTierStats = Field(description="Tier 1 (memory) statistics")
    tier2: CacheTierStats = Field(description="Tier 2 (disk) statistics")
    overall: OverallCacheStats = Field(description="Aggregate statistics")
    tracks: dict[int, Any] = Field(default_factory=dict, description="Per-track cache status")
