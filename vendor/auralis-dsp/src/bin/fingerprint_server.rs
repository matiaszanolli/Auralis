/// Fingerprinting HTTP Server (development only)
///
/// Exposes the Rust DSP fingerprinting module via HTTP REST API.
/// **Not started automatically** — must be compiled and launched manually.
/// Intended for development/testing of the fingerprint pipeline.
///
/// Endpoints:
/// - POST /fingerprint - Extract fingerprint from audio file
///   Request: {"track_id": 123, "filepath": "/path/to/file.wav"}
///   Response: {"fingerprint": {...}, "processing_time_ms": 45}
///
/// Security:
/// - Binds to 127.0.0.1 only (no network access)
/// - Filepaths are validated: must be canonical, exist, and reside under
///   the user's home directory (no arbitrary file reads)

use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

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

/// Validate that a filepath is canonical and resides under the user's home
/// directory.  Rejects path traversal, symlink escapes, and access to files
/// outside ~/Music, ~/Documents, or ~/Desktop (fixes #2631).
fn validate_filepath(raw: &str) -> Result<PathBuf, String> {
    let path = PathBuf::from(raw);

    // Canonicalize resolves symlinks and ".." components
    let canonical = fs::canonicalize(&path)
        .map_err(|e| format!("Cannot resolve path: {}", e))?;

    // Must reside under the user's home directory
    let home = dirs::home_dir()
        .ok_or_else(|| "Cannot determine home directory".to_string())?;

    let allowed_roots: Vec<PathBuf> = vec![
        home.join("Music"),
        home.join("Documents"),
        home.join("Desktop"),
    ];

    let under_allowed = allowed_roots.iter().any(|root| canonical.starts_with(root));
    if !under_allowed {
        return Err(format!(
            "Path is outside allowed directories (~/Music, ~/Documents, ~/Desktop)"
        ));
    }

    Ok(canonical)
}

/// POST /fingerprint - Extract fingerprint from audio file
async fn fingerprint_handler(
    req: web::Json<FingerprintRequest>,
) -> impl Responder {
    let start = std::time::Instant::now();

    // Validate filepath against allowed directories (fixes #2631)
    let canonical_path = match validate_filepath(&req.filepath) {
        Ok(p) => p,
        Err(msg) => {
            return HttpResponse::BadRequest().json(serde_json::json!({
                "error": msg
            }));
        }
    };

    // Check if file exists (already confirmed by canonicalize, but guard against races)
    if !canonical_path.exists() {
        return HttpResponse::NotFound().json(serde_json::json!({
            "error": "File not found"
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
    // Bind to loopback only — this is a dev-only service with no authentication.
    // Filepaths are validated to allowed directories but network binding would
    // still be unnecessary risk (fixes #2243).
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
