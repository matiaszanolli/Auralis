use axum::Json;
use crate::models::request::HealthResponse;
use std::sync::OnceLock;

static START_TIME: OnceLock<std::time::Instant> = OnceLock::new();

pub async fn health_handler() -> Json<HealthResponse> {
    let start = START_TIME.get_or_init(std::time::Instant::now);
    let uptime = start.elapsed().as_secs();

    Json(HealthResponse {
        status: "healthy".to_string(),
        version: "0.1.0".to_string(),
        uptime_sec: uptime,
    })
}
