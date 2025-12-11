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

fn main() {
    // Create Tokio runtime with aggressive thread pool configuration
    // CRITICAL: With 32 concurrent Python workers, we need both large async workers AND large blocking pool
    // - worker_threads = 32: async runtime threads for handling HTTP requests
    // - max_blocking_threads = 64: blocking thread pool for CPU-intensive fingerprint analysis
    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(32)                    // Async runtime: 32 threads for concurrency
        .max_blocking_threads(64)               // Blocking pool: 64 threads for CPU-bound work
        .thread_name("fingerprint-worker")
        .enable_all()
        .build()
        .expect("Failed to build Tokio runtime");

    rt.block_on(async {
        // Initialize logging
        tracing_subscriber::fmt()
            .with_env_filter(
                tracing_subscriber::EnvFilter::from_default_env()
                    .add_directive(tracing_subscriber::filter::LevelFilter::INFO.into()),
            )
            .init();

        tracing::info!("Starting Fingerprint Server v0.1.0");
        tracing::info!("Runtime: 32 async workers + 64 blocking threads");

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
    });
}
