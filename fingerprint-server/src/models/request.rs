use serde::{Deserialize, Serialize};
use super::Fingerprint;

#[derive(Debug, Serialize, Deserialize)]
pub struct FingerprintRequest {
    pub track_id: u32,
    pub filepath: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FingerprintResponse {
    pub track_id: u32,
    pub fingerprint: Fingerprint,
    pub metadata: AudioMetadata,
    pub processing_time_ms: u128,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AudioMetadata {
    pub duration_sec: f64,
    pub sample_rate: u32,
    pub channels: u16,
    pub format: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
    pub uptime_sec: u64,
}
