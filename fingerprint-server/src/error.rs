use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum FingerprintError {
    #[error("Audio file not found: {0}")]
    FileNotFound(String),

    #[error("Unsupported audio format: {0}")]
    UnsupportedFormat(String),

    #[error("Failed to decode audio: {0}")]
    DecodingError(String),

    #[error("Invalid audio: {0}")]
    InvalidAudio(String),

    #[error("Analysis failed: {0}")]
    AnalysisError(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Internal error: {0}")]
    InternalError(String),
}

impl IntoResponse for FingerprintError {
    fn into_response(self) -> Response {
        let (status, error_message) = match self {
            FingerprintError::FileNotFound(msg) => (StatusCode::NOT_FOUND, msg),
            FingerprintError::UnsupportedFormat(msg) => (StatusCode::UNSUPPORTED_MEDIA_TYPE, msg),
            FingerprintError::DecodingError(msg) => (StatusCode::BAD_REQUEST, msg),
            FingerprintError::InvalidAudio(msg) => (StatusCode::BAD_REQUEST, msg),
            FingerprintError::AnalysisError(msg) => (StatusCode::INTERNAL_SERVER_ERROR, msg),
            FingerprintError::IoError(err) => {
                (StatusCode::INTERNAL_SERVER_ERROR, err.to_string())
            }
            FingerprintError::InternalError(msg) => (StatusCode::INTERNAL_SERVER_ERROR, msg),
        };

        let body = Json(json!({
            "error": error_message,
        }));

        (status, body).into_response()
    }
}

pub type Result<T> = std::result::Result<T, FingerprintError>;
