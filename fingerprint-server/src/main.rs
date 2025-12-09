mod api;
mod audio;
mod analysis;
mod error;
mod models;

use axum::{
    routing::{get, post},
    Router,
};
use std::net::SocketAddr;
use tower_http::cors::CorsLayer;
use tracing_subscriber;

#[tokio::main]
async fn main() {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive(tracing_subscriber::filter::LevelFilter::INFO.into()),
        )
        .init();

    tracing::info!("Starting Fingerprint Server v0.1.0");

    // Build router
    let app = Router::new()
        .route("/health", get(api::health::health_handler))
        .route("/fingerprint", post(api::fingerprint::fingerprint_handler))
        .layer(CorsLayer::permissive())
        .layer(tower_http::trace::TraceLayer::new_for_http());

    // Bind to socket
    let addr = SocketAddr::from(([127, 0, 0, 1], 8766));
    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .expect("Failed to bind to port 8766");

    tracing::info!("Server listening on {}", addr);

    // Run server
    axum::serve(listener, app)
        .await
        .expect("Server error");
}
