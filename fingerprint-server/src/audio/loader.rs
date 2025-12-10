use crate::error::{FingerprintError, Result};
use std::fs::File;
use symphonia::core::audio::{AudioBufferRef, Signal};
use symphonia::core::codecs::DecoderOptions;
use symphonia::core::formats::FormatOptions;
use symphonia::core::io::MediaSourceStream;
use symphonia::core::probe::Hint;

use std::sync::Arc;

#[derive(Debug, Clone)]
pub struct AudioData {
    // Use Arc to enable cheap cloning without duplicating samples
    // Multiple workers can share the same audio buffer without copies
    pub samples: Arc<Vec<f64>>,
    pub sample_rate: u32,
    pub channels: u16,
}

/// Load audio from file path and return samples + metadata
///
/// Supports: WAV, FLAC, MP3, AAC, OGG, M4A, WMA
/// Always returns mono (averages channels if stereo)
pub async fn load_audio(filepath: &str) -> Result<AudioData> {
    // Check file exists
    if !std::path::Path::new(filepath).exists() {
        return Err(FingerprintError::FileNotFound(filepath.to_string()));
    }

    // Spawn blocking since file I/O is synchronous
    let filepath = filepath.to_string();
    tokio::task::spawn_blocking(move || load_audio_sync(&filepath))
        .await
        .map_err(|e| FingerprintError::InternalError(format!("Task join error: {}", e)))?
}

fn load_audio_sync(filepath: &str) -> Result<AudioData> {
    tracing::debug!("Loading audio from: {}", filepath);

    // Detect format from file extension FIRST
    let detected_format = detect_format_from_extension(filepath)?;
    tracing::info!("Detected format from extension '{}': {}",
        std::path::Path::new(filepath)
            .extension()
            .map(|e| e.to_string_lossy().into_owned())
            .unwrap_or_else(|| "no extension".to_string()),
        detected_format
    );

    // MP3 support enabled - Symphonia handles MP3 decoding

    // Create hint with detected format to guide Symphonia's probe
    let mut hint = Hint::new();
    hint.with_extension(&detected_format);
    tracing::debug!("Using format hint: {}", detected_format);

    // Open file for probing
    let file = File::open(filepath)
        .map_err(|e| FingerprintError::FileNotFound(format!("{}: {}", filepath, e)))?;

    use symphonia::core::io::ReadOnlySource;
    let source = ReadOnlySource::new(file);
    let mss = MediaSourceStream::new(Box::new(source), Default::default());

    // Probe format with detected format hint
    // Note: Symphonia's probe will try formats internally, but the hint guides prioritization
    let probed = symphonia::default::get_probe()
        .format(
            &hint,
            mss,
            &FormatOptions::default(),
            &Default::default(),
        )
        .map_err(|e| {
            let error_msg = format!("{}", e);
            tracing::error!("Failed to probe format '{}' for {}: {}", detected_format, filepath, error_msg);

            // Detect if file is corrupted (end of stream, truncated, etc.)
            if error_msg.contains("end of stream") || error_msg.contains("truncated") || error_msg.contains("unexpected end") {
                FingerprintError::InvalidAudio(format!(
                    "File appears corrupted or truncated ({}): {}",
                    detected_format, error_msg
                ))
            } else {
                FingerprintError::UnsupportedFormat(format!(
                    "Failed to probe format '{}': {}",
                    detected_format, error_msg
                ))
            }
        })?;

    tracing::info!("Successfully probed format '{}' for: {}", detected_format, filepath);
    let mut format = probed.format;

    tracing::debug!("Format reader created successfully for: {}", filepath);

    let track = format
        .tracks()
        .iter()
        .find(|t| t.codec_params.sample_rate.is_some())
        .ok_or_else(|| FingerprintError::InvalidAudio("No audio tracks found".to_string()))?;

    let sample_rate = track
        .codec_params
        .sample_rate
        .ok_or_else(|| FingerprintError::InvalidAudio("No sample rate found".to_string()))?;
    let channels = track
        .codec_params
        .channels
        .ok_or_else(|| FingerprintError::InvalidAudio("No channel info found".to_string()))?
        .count() as u16;

    tracing::debug!(
        "Audio format: {} Hz, {} channels",
        sample_rate,
        channels
    );

    // Decode all samples
    let mut samples = Vec::new();
    let mut decoder = symphonia::default::get_codecs()
        .make(
            &track.codec_params,
            &DecoderOptions::default(),
        )
        .map_err(|e| FingerprintError::DecodingError(format!("Decoder error: {}", e)))?;

    loop {
        match format.next_packet() {
            Ok(packet) => {
                match decoder.decode(&packet) {
                    Ok(buf) => {
                        collect_samples(&mut samples, &buf, channels as usize)?;
                    }
                    Err(symphonia::core::errors::Error::DecodeError(_)) => {
                        // Skip frames that can't be decoded
                        continue;
                    }
                    Err(e) => return Err(FingerprintError::DecodingError(format!("{}", e))),
                }
            }
            Err(symphonia::core::errors::Error::IoError(_)) => break,
            Err(symphonia::core::errors::Error::Unsupported(_)) => break,
            Err(e) => return Err(FingerprintError::DecodingError(format!("{}", e))),
        }
    }

    // Validate audio
    if samples.is_empty() {
        return Err(FingerprintError::InvalidAudio(
            "No audio samples decoded".to_string(),
        ));
    }

    if !samples.iter().all(|s| s.is_finite()) {
        return Err(FingerprintError::InvalidAudio(
            "Audio contains NaN or infinite values".to_string(),
        ));
    }

    tracing::debug!(
        "Loaded {} samples at {} Hz from {}",
        samples.len(),
        sample_rate,
        filepath
    );

    Ok(AudioData {
        samples: Arc::new(samples),
        sample_rate,
        channels,
    })
}

fn collect_samples(
    samples: &mut Vec<f64>,
    buf: &AudioBufferRef,
    channels: usize,
) -> Result<()> {
    // Helper macro to avoid code duplication
    macro_rules! process_buffer {
        ($buf:expr, $norm_fn:expr) => {{
            if $buf.frames() == 0 {
                return Ok(());
            }
            let n_frames = $buf.frames();
            let ch_count = std::cmp::min(channels, $buf.spec().channels.count());
            for frame_idx in 0..n_frames {
                let mut sum = 0.0f64;
                for ch in 0..ch_count {
                    sum += $norm_fn($buf.chan(ch)[frame_idx]);
                }
                samples.push(sum / ch_count as f64);
            }
        }};
    }

    match buf {
        // Float formats
        AudioBufferRef::F32(fbuf) => {
            process_buffer!(fbuf, |v: f32| v as f64)
        }
        AudioBufferRef::F64(fbuf) => {
            process_buffer!(fbuf, |v: f64| v)
        }
        // Signed integer formats
        AudioBufferRef::S8(ibuf) => {
            process_buffer!(ibuf, |v: i8| v as f64 / i8::MAX as f64)
        }
        AudioBufferRef::S16(ibuf) => {
            process_buffer!(ibuf, |v: i16| v as f64 / i16::MAX as f64)
        }
        AudioBufferRef::S24(ibuf) => {
            process_buffer!(ibuf, |v: symphonia::core::sample::i24| v.into_i32() as f64 / (2_i32.pow(23) - 1) as f64)
        }
        AudioBufferRef::S32(ibuf) => {
            process_buffer!(ibuf, |v: i32| v as f64 / i32::MAX as f64)
        }
        // Unsigned integer formats (center at 0)
        AudioBufferRef::U8(ubuf) => {
            process_buffer!(ubuf, |v: u8| ((v as f64 / 255.0) - 0.5) * 2.0)
        }
        AudioBufferRef::U16(ubuf) => {
            process_buffer!(ubuf, |v: u16| ((v as f64 / 65535.0) - 0.5) * 2.0)
        }
        AudioBufferRef::U24(ubuf) => {
            process_buffer!(ubuf, |v: symphonia::core::sample::u24| {
                let norm = v.into_u32() as f64 / (2_u32.pow(24) - 1) as f64;
                (norm - 0.5) * 2.0
            })
        }
        AudioBufferRef::U32(ubuf) => {
            process_buffer!(ubuf, |v: u32| ((v as f64 / u32::MAX as f64) - 0.5) * 2.0)
        }
    }
    Ok(())
}

/// Detect audio format from file extension
///
/// Uses file extension to determine the audio format before passing to Symphonia.
/// This ensures the correct format decoder is used and prevents format detection errors.
///
/// Supports: WAV, FLAC, MP3, AAC, OGG, M4A, AIFF, WMA, MKV, WebM, DSD, OPUS, AU, MOV, etc.
fn detect_format_from_extension(filepath: &str) -> Result<String> {
    let ext = std::path::Path::new(filepath)
        .extension()
        .ok_or_else(|| FingerprintError::InvalidAudio(
            format!("File has no extension: {}", filepath)
        ))?
        .to_string_lossy()
        .to_lowercase();

    // Normalize common extension variations to standard format names
    // These are the exact format names Symphonia expects
    let normalized = match ext.as_str() {
        // WAV variants
        "wav" | "wave" => "wav",

        // FLAC (most common in music libraries)
        "flac" => "flac",

        // MP3 variants
        "mp3" | "mpeg" | "mpg" => "mp3",

        // MPEG-4 variants
        "m4a" | "m4b" | "m4v" | "mp4" => "m4a",

        // OGG variants (Vorbis)
        "ogg" | "oga" | "ogx" => "ogg",

        // OPUS (OGG container)
        "opus" => "ogg",

        // AAC variants (ADTS)
        "aac" | "adts" => "aac",

        // AIFF variants
        "aiff" | "aif" | "aifc" | "aiffc" => "aiff",

        // WMA
        "wma" | "wmv" => "wma",

        // Matroska
        "mkv" | "mka" | "mks" => "mkv",

        // WebM
        "webm" | "weba" => "webm",

        // DSD (often used for hi-res audio)
        "dsd" | "dsf" | "dff" => "dsd",

        // MOV (QuickTime)
        "mov" | "qt" => "mov",

        // AU (Sun audio)
        "au" | "snd" => "au",

        // ALAC (Apple Lossless)
        "alac" => "alac",

        // Other formats
        "flv" => "flv",
        "mxf" => "mxf",
        "vorbis" => "ogg",

        // Fallback: use the extension as-is and let Symphonia handle it
        unknown => unknown,
    };

    Ok(normalized.to_string())
}
