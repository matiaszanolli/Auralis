# -*- coding: utf-8 -*-

"""
Similarity API Router
~~~~~~~~~~~~~~~~~~~~

REST API endpoints for fingerprint-based music similarity

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from auralis.analysis.fingerprint import (
    FingerprintSimilarity,
    KNNGraphBuilder,
    SimilarityResult
)
from auralis.library import LibraryManager


# Response models
class SimilarTrack(BaseModel):
    """Similar track response model"""
    track_id: int = Field(..., description="ID of the similar track")
    distance: float = Field(..., description="Fingerprint distance (lower = more similar)")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score 0-1 (higher = more similar)")
    rank: Optional[int] = Field(None, description="Rank in similarity (1=most similar)")

    # Optional track details
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None


class SimilarityExplanation(BaseModel):
    """Detailed similarity explanation"""
    track_id1: int
    track_id2: int
    distance: float
    similarity_score: float
    top_differences: List[Dict[str, float]]


class GraphStatsResponse(BaseModel):
    """Similarity graph statistics"""
    total_tracks: int
    total_edges: int
    k_neighbors: int
    avg_distance: float
    min_distance: float
    max_distance: float
    build_time_seconds: Optional[float] = None


def create_similarity_router(
    get_library_manager,
    get_similarity_system,
    get_graph_builder
) -> APIRouter:
    """
    Create similarity API router with dependency injection

    Args:
        get_library_manager: Callable that returns LibraryManager instance
        get_similarity_system: Callable that returns FingerprintSimilarity instance
        get_graph_builder: Callable that returns KNNGraphBuilder instance

    Returns:
        Configured FastAPI router
    """
    router = APIRouter(prefix="/api/similarity", tags=["similarity"])

    @router.get("/tracks/{track_id}/similar", response_model=List[SimilarTrack])
    async def get_similar_tracks(
        track_id: int,
        limit: int = Query(10, ge=1, le=100, description="Number of similar tracks to return"),
        use_graph: bool = Query(True, description="Use pre-computed graph if available"),
        include_details: bool = Query(False, description="Include track title/artist/album")
    ):
        """
        Get similar tracks to a given track

        Uses fingerprint-based similarity to find acoustically similar tracks,
        enabling cross-genre music discovery.

        Args:
            track_id: ID of the target track
            limit: Maximum number of similar tracks (1-100)
            use_graph: Use pre-computed K-NN graph if available (faster)
            include_details: Include track metadata in response

        Returns:
            List of similar tracks sorted by similarity (most similar first)
        """
        try:
            library = get_library_manager()

            # Check if track exists
            track = library.get_track(track_id)
            if not track:
                raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

            # Check if track has fingerprint
            if not library.fingerprints.exists(track_id):
                raise HTTPException(
                    status_code=400,
                    detail=f"Track {track_id} does not have a fingerprint. Run fingerprint extraction first."
                )

            results = []

            if use_graph:
                # Use pre-computed graph (fastest)
                graph_builder = get_graph_builder()

                # Check if graph_builder exists (may be None if not fitted)
                if graph_builder is None:
                    use_graph = False
                else:
                    neighbors = graph_builder.get_neighbors(track_id, limit=limit)

                    if neighbors:
                        # Convert to SimilarTrack objects
                        for neighbor in neighbors:
                            result = SimilarTrack(
                                track_id=neighbor['similar_track_id'],
                                distance=neighbor['distance'],
                                similarity_score=neighbor['similarity_score'],
                                rank=neighbor['rank']
                            )

                            if include_details:
                                similar_track = library.get_track(neighbor['similar_track_id'])
                                if similar_track:
                                    result.title = similar_track.title
                                    result.artist = similar_track.artists[0].name if similar_track.artists else None
                                    result.album = similar_track.album.title if similar_track.album else None

                            results.append(result)
                    else:
                        # Graph not built yet, fall back to real-time calculation
                        use_graph = False

            if not use_graph:
                # Real-time calculation (slower but always available)
                similarity = get_similarity_system()

                if not similarity.is_fitted():
                    raise HTTPException(
                        status_code=503,
                        detail="Similarity system not initialized. Please wait for initialization."
                    )

                similarity_results = similarity.find_similar(track_id, n=limit)

                for i, result in enumerate(similarity_results, start=1):
                    similar_track_model = SimilarTrack(
                        track_id=result.track_id,
                        distance=result.distance,
                        similarity_score=result.similarity_score,
                        rank=i
                    )

                    if include_details:
                        similar_track = library.get_track(result.track_id)
                        if similar_track:
                            similar_track_model.title = similar_track.title
                            similar_track_model.artist = similar_track.artists[0].name if similar_track.artists else None
                            similar_track_model.album = similar_track.album.title if similar_track.album else None

                    results.append(similar_track_model)

            return results

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error finding similar tracks: {str(e)}")

    @router.get("/tracks/{track_id1}/compare/{track_id2}", response_model=SimilarTrack)
    async def compare_tracks(
        track_id1: int,
        track_id2: int
    ):
        """
        Compare two specific tracks for similarity

        Args:
            track_id1: First track ID
            track_id2: Second track ID

        Returns:
            Similarity between the two tracks
        """
        try:
            library = get_library_manager()

            # Check if tracks exist
            track1 = library.get_track(track_id1)
            track2 = library.get_track(track_id2)

            if not track1:
                raise HTTPException(status_code=404, detail=f"Track {track_id1} not found")
            if not track2:
                raise HTTPException(status_code=404, detail=f"Track {track_id2} not found")

            # Check fingerprints
            if not library.fingerprints.exists(track_id1):
                raise HTTPException(status_code=400, detail=f"Track {track_id1} missing fingerprint")
            if not library.fingerprints.exists(track_id2):
                raise HTTPException(status_code=400, detail=f"Track {track_id2} missing fingerprint")

            # Calculate similarity
            similarity = get_similarity_system()

            if not similarity.is_fitted():
                raise HTTPException(status_code=503, detail="Similarity system not initialized")

            result = similarity.calculate_similarity(track_id1, track_id2)

            if not result:
                raise HTTPException(status_code=500, detail="Failed to calculate similarity")

            return SimilarTrack(
                track_id=track_id2,
                distance=result.distance,
                similarity_score=result.similarity_score,
                title=track2.title,
                artist=track2.artists[0].name if track2.artists else None,
                album=track2.album.title if track2.album else None
            )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error comparing tracks: {str(e)}")

    @router.get("/tracks/{track_id1}/explain/{track_id2}", response_model=SimilarityExplanation)
    async def explain_similarity(
        track_id1: int,
        track_id2: int,
        top_n: int = Query(5, ge=1, le=25, description="Number of top contributing dimensions")
    ):
        """
        Explain why two tracks are similar/different

        Returns the top dimensions contributing to similarity/difference.

        Args:
            track_id1: First track ID
            track_id2: Second track ID
            top_n: Number of top dimensions to return

        Returns:
            Detailed explanation of similarity
        """
        try:
            similarity = get_similarity_system()

            if not similarity.is_fitted():
                raise HTTPException(status_code=503, detail="Similarity system not initialized")

            explanation = similarity.get_similarity_explanation(track_id1, track_id2, top_n=top_n)

            if not explanation:
                raise HTTPException(status_code=404, detail="Could not generate explanation")

            return SimilarityExplanation(**explanation)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error explaining similarity: {str(e)}")

    @router.post("/fit")
    async def fit_similarity_system(
        min_samples: int = Query(10, ge=5, description="Minimum fingerprints required to fit")
    ) -> Dict[str, Any]:
        """
        Fit the similarity system with current fingerprints

        The similarity system must be fitted before building the K-NN graph
        or performing similarity searches.

        Args:
            min_samples: Minimum number of fingerprints required

        Returns:
            Status and fitted track count
        """
        try:
            library = get_library_manager()
            similarity = get_similarity_system()

            if similarity is None:
                raise HTTPException(status_code=503, detail="Similarity system not available")

            # Check if already fitted
            if similarity.is_fitted():
                count = similarity.get_fitted_track_count()
                return {
                    "fitted": True,
                    "total_fingerprints": count,
                    "message": f"Similarity system already fitted with {count} tracks"
                }

            # Get fingerprint count
            fingerprint_count = library.fingerprints.get_count()

            if fingerprint_count < min_samples:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient fingerprints: {fingerprint_count} < {min_samples}"
                )

            # Fit the similarity system
            similarity.fit()

            return {
                "fitted": True,
                "total_fingerprints": fingerprint_count,
                "message": f"Successfully fitted similarity system with {fingerprint_count} tracks"
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fitting similarity system: {str(e)}")

    @router.post("/graph/build")
    async def build_similarity_graph(
        k: int = Query(10, ge=1, le=50, description="Number of neighbors per track"),
        clear_existing: bool = Query(True, description="Clear existing graph before building")
    ) -> GraphStatsResponse:
        """
        Build K-nearest neighbors similarity graph

        Pre-computes similarity relationships for fast queries.
        This can take several minutes for large libraries.

        Args:
            k: Number of similar tracks to find for each track
            clear_existing: Whether to clear existing graph

        Returns:
            Graph build statistics
        """
        try:
            graph_builder = get_graph_builder()

            if graph_builder is None:
                raise HTTPException(
                    status_code=503,
                    detail="Similarity system not fitted. Please fit the system first using POST /api/similarity/fit"
                )

            stats = graph_builder.build_graph(k=k, clear_existing=clear_existing)

            return GraphStatsResponse(**stats.to_dict())

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error building graph: {str(e)}")

    @router.get("/graph/stats", response_model=Optional[GraphStatsResponse])
    async def get_graph_stats():
        """
        Get statistics about current similarity graph

        Returns:
            Graph statistics or null if graph not built
        """
        try:
            graph_builder = get_graph_builder()

            if graph_builder is None:
                return None

            stats = graph_builder.get_graph_stats()

            if stats:
                return GraphStatsResponse(**stats.to_dict())
            else:
                return None

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting graph stats: {str(e)}")

    @router.delete("/graph")
    async def clear_similarity_graph() -> Dict[str, Any]:
        """
        Clear the similarity graph

        Returns:
            Number of edges deleted
        """
        try:
            graph_builder = get_graph_builder()

            if graph_builder is None:
                return {"edges_deleted": 0}

            count = graph_builder.clear_graph()

            return {"edges_deleted": count}

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error clearing graph: {str(e)}")

    return router
