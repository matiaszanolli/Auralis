#!/usr/bin/env python3
"""
gRPC Fingerprint Client - Rust DSP Backend

Uses librosa for audio loading (fast C++ backend) and streams audio
to Rust gRPC server for DSP processing.

Architecture:
- Python: Audio loading (librosa)
- gRPC: Binary streaming (Protocol Buffers)
- Rust: DSP computation (HPSS, YIN, Chroma, Tempo)
- Python: Database storage (SQLite)
"""

import grpc
import numpy as np
import librosa
from pathlib import Path
from typing import Optional, Dict

import fingerprint_pb2
import fingerprint_pb2_grpc


class GrpcFingerprintClient:
    """Client for Rust gRPC fingerprint server"""

    def __init__(self, server_address: str = "[::1]:50051"):
        self.server_address = server_address
        self.channel = None
        self.stub = None

    def connect(self):
        """Connect to gRPC server"""
        # Increase message size limits for audio streaming (200MB for long tracks)
        options = [
            ('grpc.max_send_message_length', 200 * 1024 * 1024),  # 200MB
            ('grpc.max_receive_message_length', 200 * 1024 * 1024),  # 200MB
        ]
        self.channel = grpc.insecure_channel(self.server_address, options=options)
        self.stub = fingerprint_pb2_grpc.FingerprintServiceStub(self.channel)

    def close(self):
        """Close gRPC connection"""
        if self.channel:
            self.channel.close()

    def compute_fingerprint(self, track_id: int, filepath: str) -> Optional[Dict]:
        """
        Compute 25D audio fingerprint using Rust DSP

        Args:
            track_id: Track ID for logging
            filepath: Path to audio file

        Returns:
            Dictionary with 25 dimensions or None on error
        """
        try:
            # Load audio with librosa (C++ backend)
            # Downsample to 22050 Hz for fingerprinting (reduces message size)
            audio, sr = librosa.load(str(filepath), sr=22050, mono=True)

            # Convert to float32 for gRPC
            audio_samples = audio.astype(np.float32).tolist()

            # Create gRPC request
            request = fingerprint_pb2.FingerprintRequest(
                track_id=track_id,
                audio_samples=audio_samples,
                sample_rate=sr,
                channels=1  # mono
            )

            # Call Rust server
            response = self.stub.ComputeFingerprint(request)

            # Convert response to dictionary
            fingerprint = {
                # Frequency Distribution (7D)
                'sub_bass_pct': response.sub_bass_pct,
                'bass_pct': response.bass_pct,
                'low_mid_pct': response.low_mid_pct,
                'mid_pct': response.mid_pct,
                'upper_mid_pct': response.upper_mid_pct,
                'presence_pct': response.presence_pct,
                'air_pct': response.air_pct,

                # Dynamics (3D)
                'lufs': response.lufs,
                'crest_db': response.crest_db,
                'bass_mid_ratio': response.bass_mid_ratio,

                # Temporal (4D)
                'tempo_bpm': response.tempo_bpm,
                'rhythm_stability': response.rhythm_stability,
                'transient_density': response.transient_density,
                'silence_ratio': response.silence_ratio,

                # Spectral (3D)
                'spectral_centroid': response.spectral_centroid,
                'spectral_rolloff': response.spectral_rolloff,
                'spectral_flatness': response.spectral_flatness,

                # Harmonic (3D)
                'harmonic_ratio': response.harmonic_ratio,
                'pitch_stability': response.pitch_stability,
                'chroma_energy': response.chroma_energy,

                # Variation (3D)
                'dynamic_range_variation': response.dynamic_range_variation,
                'loudness_variation_std': response.loudness_variation_std,
                'peak_consistency': response.peak_consistency,

                # Stereo (2D)
                'stereo_width': response.stereo_width,
                'phase_correlation': response.phase_correlation,
            }

            print(f"  ✅ Fingerprint computed in {response.processing_time_ms}ms")
            return fingerprint

        except grpc.RpcError as e:
            print(f"  ⚠️  gRPC error: {e.code()} - {e.details()}")
            return None
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
            return None


def test_client():
    """Test the gRPC client with a sample audio file"""
    client = GrpcFingerprintClient()

    try:
        print("🎵 Connecting to gRPC server...")
        client.connect()

        # Find a test audio file
        import sqlite3
        conn = sqlite3.connect('/home/matias/.auralis/library.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, filepath FROM tracks LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            track_id, filepath = row
            print(f"📝 Testing with track {track_id}: {Path(filepath).name}")

            fingerprint = client.compute_fingerprint(track_id, filepath)

            if fingerprint:
                print("\n✅ Fingerprint computed successfully!")
                print(f"   Tempo: {fingerprint['tempo_bpm']:.1f} BPM")
                print(f"   LUFS: {fingerprint['lufs']:.1f} dB")
                print(f"   Harmonic ratio: {fingerprint['harmonic_ratio']:.2f}")
            else:
                print("❌ Failed to compute fingerprint")
        else:
            print("❌ No tracks found in database")

    finally:
        client.close()
        print("\n🔌 Disconnected from gRPC server")


if __name__ == "__main__":
    test_client()
