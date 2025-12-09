use axum::{Json, http::StatusCode};
use std::time::Instant;
use crate::models::request::{FingerprintRequest, FingerprintResponse, AudioMetadata};
use crate::audio::loader::load_audio;
use crate::analysis::analyzer::analyze_fingerprint;
use crate::error::Result;

pub async fn fingerprint_handler(
    Json(req): Json<FingerprintRequest>,
) -> Result<(StatusCode, Json<FingerprintResponse>)> {
    let start = Instant::now();

    tracing::debug!("Processing fingerprint request for track {}: {}", req.track_id, req.filepath);

    // Load audio asynchronously (I/O bound)
    let audio_data = load_audio(&req.filepath).await?;

    tracing::debug!(
        "Loaded audio: {} samples at {} Hz, {} channels",
        audio_data.samples.len(),
        audio_data.sample_rate,
        audio_data.channels
    );

    // Analyze fingerprint (CPU bound, spawn blocking to not block async runtime)
    let audio_data_clone = audio_data.clone();
    let fingerprint = tokio::task::spawn_blocking(move || {
        analyze_fingerprint(&audio_data_clone.samples, audio_data_clone.sample_rate)
    })
    .await
    .map_err(|e| crate::error::FingerprintError::AnalysisError(format!("Task join error: {}", e)))??;

    tracing::debug!("Fingerprint analysis complete for track {}", req.track_id);

    // Calculate duration
    let duration_sec = audio_data.samples.len() as f64 / audio_data.sample_rate as f64;

    let response = FingerprintResponse {
        track_id: req.track_id,
        fingerprint,
        metadata: AudioMetadata {
            duration_sec,
            sample_rate: audio_data.sample_rate,
            channels: audio_data.channels,
            format: infer_format(&req.filepath),
        },
        processing_time_ms: start.elapsed().as_millis(),
    };

    tracing::info!(
        "Successfully fingerprinted track {} in {}ms",
        req.track_id,
        response.processing_time_ms
    );

    Ok((StatusCode::OK, Json(response)))
}

fn infer_format(filepath: &str) -> String {
    filepath
        .split('.')
        .last()
        .unwrap_or("unknown")
        .to_lowercase()
}
