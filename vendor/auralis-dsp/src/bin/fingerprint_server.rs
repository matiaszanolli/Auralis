/// Fingerprinting HTTP Server
///
/// Exposes the Rust DSP fingerprinting module via HTTP REST API
/// Handles concurrent fingerprint extraction requests with high performance
///
/// Endpoints:
/// - POST /fingerprint - Extract fingerprint from audio file
///   Request: {"track_id": 123, "filepath": "/path/to/file.wav"}
///   Response: {"fingerprint": {...}, "processing_time_ms": 45}

use std::sync::Arc;
use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use serde::{Deserialize, Serialize};
use std::fs;

#[derive(Debug, Serialize, Deserialize)]
struct FingerprintRequest {
    track_id: u32,
    filepath: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct FingerprintResponse {
    fingerprint: std::collections::HashMap<String, f32>,
    processing_time_ms: u64,
    track_id: u32,
}

/// POST /fingerprint - Extract fingerprint from audio file
async fn fingerprint_handler(
    req: web::Json<FingerprintRequest>,
) -> impl Responder {
    let start = std::time::Instant::now();

    // Check if file exists
    if !fs::metadata(&req.filepath).is_ok() {
        return HttpResponse::NotFound().json(serde_json::json!({
            "error": "File not found",
            "filepath": req.filepath
        }));
    }

    // In a real implementation, this would call the Rust DSP library
    // For now, return a placeholder response
    let fingerprint: std::collections::HashMap<String, f32> = (0..25)
        .map(|i| (format!("dimension_{}", i), 0.5))
        .collect();

    let elapsed = start.elapsed().as_millis() as u64;

    let response = FingerprintResponse {
        fingerprint,
        processing_time_ms: elapsed,
        track_id: req.track_id,
    };

    HttpResponse::Ok().json(response)
}

/// Health check endpoint
async fn health() -> impl Responder {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "ok",
        "service": "auralis-fingerprint-server",
        "version": "1.0.0"
    }))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // Bind to loopback only — this service has no authentication and accepts
    // arbitrary file paths in POST requests, so network-accessible binding
    // would be a significant security risk (fixes #2243).
    println!("🎵 Auralis Fingerprint Server starting on http://127.0.0.1:8766");

    HttpServer::new(|| {
        App::new()
            .route("/health", web::get().to(health))
            .route("/fingerprint", web::post().to(fingerprint_handler))
    })
    .bind("127.0.0.1:8766")?
    .run()
    .await
}
