//! Librosa-compatible temporal analysis: beat tracking + silence ratio.
//!
//! Ports the Python fallback's `rhythm_stability` and `silence_ratio` so the
//! Rust (default) path and the Python path produce convergent fingerprint
//! values (#4113). Previously the Rust analyzer derived `rhythm_stability` from
//! the coefficient of variation of 100 ms RMS frames (a *loudness* metric) and
//! `silence_ratio` from a single global RMS vs a −60 dB threshold — both
//! algorithmically incompatible with Python.
//!
//! Reference implementation: librosa 0.11.0.
//!   - `rhythm_stability`: `onset_strength` (log-power mel spectral flux) →
//!     `beat_track` (tempogram tempo estimate + dynamic-programming tracker) →
//!     `1 / (1 + CV(inter-beat intervals))`.
//!   - `silence_ratio`: per-frame RMS, fraction of frames more than 40 dB below
//!     the loudest frame (i.e. `rms < 0.01 * max_rms`).
//!
//! Every stage mirrors the corresponding librosa routine with the same default
//! parameters (n_fft=2048, hop=512, n_mels=128, Slaney mel, tempogram
//! win_length=384, start_bpm=120, std_bpm=1.0, max_tempo=320, tightness=100).

use rustfft::num_complex::Complex;
use rustfft::FftPlanner;
use std::f64::consts::PI;

const N_FFT: usize = 2048;
const HOP: usize = 512;
const N_MELS: usize = 128;
const N_BINS: usize = N_FFT / 2 + 1; // 1025
const TG_WIN: usize = 384; // tempogram window (frames) ≈ 8.9 s @ 512/44.1k

// ---------------------------------------------------------------------------
// Public entry points
// ---------------------------------------------------------------------------

/// Rhythm stability in [0, 1]: `1 / (1 + CV(inter-beat intervals))`.
/// Mirrors `TemporalOperations.calculate_rhythm_stability`. Returns 0.5 if the
/// pipeline cannot produce an estimate (matches the Python except-fallback),
/// 0.0 if fewer than 3 beats are detected.
pub fn rhythm_stability(samples: &[f64], sample_rate: u32) -> f64 {
    let onset_env = match onset_strength(samples, sample_rate) {
        Some(o) if o.iter().any(|&v| v != 0.0) => o,
        _ => return 0.5,
    };

    let bpm = estimate_tempo(&onset_env, sample_rate);
    if !(bpm > 0.0) {
        return 0.5;
    }

    let beats = beat_track(&onset_env, bpm, sample_rate);
    if beats.len() < 3 {
        return 0.0; // Not enough beats to measure stability (Python parity)
    }

    // beat frames → seconds → inter-beat intervals
    let frame_rate = sample_rate as f64 / HOP as f64;
    let intervals: Vec<f64> = beats
        .windows(2)
        .map(|w| (w[1] as f64 - w[0] as f64) / frame_rate)
        .collect();
    if intervals.len() < 2 {
        return 0.0;
    }

    let mean = intervals.iter().sum::<f64>() / intervals.len() as f64;
    if mean <= 1e-9 {
        return 0.5;
    }
    // Population std (np.std default ddof=0), CV = std / mean, scale = 1.0.
    let var = intervals.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / intervals.len() as f64;
    let cv = var.sqrt() / mean;
    (1.0 / (1.0 + cv)).clamp(0.0, 1.0)
}

/// Silence ratio in [0, 1]: fraction of RMS frames more than 40 dB below the
/// loudest frame. Mirrors `TemporalOperations.calculate_silence_ratio`
/// (`librosa.amplitude_to_db(rms, ref=np.max) < -40`).
pub fn silence_ratio(samples: &[f64]) -> f64 {
    let rms = framed_rms(samples);
    if rms.is_empty() {
        return 0.1; // Python's failure default
    }
    let max_rms = rms.iter().cloned().fold(0.0_f64, f64::max);
    if max_rms <= 0.0 {
        return 1.0;
    }
    // rms_db = 20*log10(rms/max_rms) < -40  ⇔  rms < max_rms * 10^(-2)
    let threshold = max_rms * 0.01;
    let silent = rms.iter().filter(|&&r| r < threshold).count();
    (silent as f64 / rms.len() as f64).clamp(0.0, 1.0)
}

// ---------------------------------------------------------------------------
// Onset strength (log-power mel spectral flux)
// ---------------------------------------------------------------------------

/// Periodic Hann window of length `n` (scipy get_window fftbins=True).
fn hann_periodic(n: usize) -> Vec<f64> {
    (0..n)
        .map(|i| 0.5 - 0.5 * (2.0 * PI * i as f64 / n as f64).cos())
        .collect()
}

/// Power STFT with librosa defaults: center=True, constant (zero) padding of
/// n_fft//2, periodic Hann window, power=2.0. Returns `n_frames` columns each
/// holding `N_BINS` power values.
fn stft_power(samples: &[f64], fft: &std::sync::Arc<dyn rustfft::Fft<f64>>) -> Vec<Vec<f64>> {
    let pad = N_FFT / 2;
    let mut y = vec![0.0_f64; samples.len() + 2 * pad];
    y[pad..pad + samples.len()].copy_from_slice(samples);

    if y.len() < N_FFT {
        return Vec::new();
    }
    let n_frames = 1 + (y.len() - N_FFT) / HOP;
    let window = hann_periodic(N_FFT);
    let mut frames = Vec::with_capacity(n_frames);
    let mut buf = vec![Complex { re: 0.0, im: 0.0 }; N_FFT];

    for t in 0..n_frames {
        let start = t * HOP;
        for i in 0..N_FFT {
            buf[i].re = y[start + i] * window[i];
            buf[i].im = 0.0;
        }
        fft.process(&mut buf);
        let mut col = vec![0.0_f64; N_BINS];
        for (k, c) in buf.iter().take(N_BINS).enumerate() {
            col[k] = c.re * c.re + c.im * c.im; // power (|stft|^2)
        }
        frames.push(col);
    }
    frames
}

/// Slaney mel filterbank (n_mels × N_BINS), `norm='slaney'`, fmin=0, fmax=sr/2.
fn mel_filterbank(sample_rate: u32) -> Vec<Vec<f64>> {
    let sr = sample_rate as f64;
    let fmax = sr / 2.0;

    // fft_frequencies: linspace(0, sr/2, N_BINS)
    let fftfreqs: Vec<f64> = (0..N_BINS)
        .map(|k| k as f64 * fmax / (N_BINS as f64 - 1.0))
        .collect();

    // Slaney hz<->mel
    let f_sp = 200.0 / 3.0;
    let min_log_hz = 1000.0;
    let min_log_mel = min_log_hz / f_sp; // (1000 - 0)/f_sp = 15.0
    let logstep = (6.4_f64).ln() / 27.0;
    let hz_to_mel = |f: f64| -> f64 {
        if f >= min_log_hz {
            min_log_mel + (f / min_log_hz).ln() / logstep
        } else {
            f / f_sp
        }
    };
    let mel_to_hz = |m: f64| -> f64 {
        if m >= min_log_mel {
            min_log_hz * (logstep * (m - min_log_mel)).exp()
        } else {
            f_sp * m
        }
    };

    // mel_frequencies(n_mels+2, fmin=0, fmax)
    let min_mel = hz_to_mel(0.0);
    let max_mel = hz_to_mel(fmax);
    let n_pts = N_MELS + 2;
    let mel_f: Vec<f64> = (0..n_pts)
        .map(|i| mel_to_hz(min_mel + (max_mel - min_mel) * i as f64 / (n_pts as f64 - 1.0)))
        .collect();

    let fdiff: Vec<f64> = mel_f.windows(2).map(|w| w[1] - w[0]).collect();

    let mut weights = vec![vec![0.0_f64; N_BINS]; N_MELS];
    for i in 0..N_MELS {
        for (k, &fq) in fftfreqs.iter().enumerate() {
            let lower = (fq - mel_f[i]) / fdiff[i]; // = -ramps[i]/fdiff[i]
            let upper = (mel_f[i + 2] - fq) / fdiff[i + 1]; // = ramps[i+2]/fdiff[i+1]
            let w = lower.min(upper).max(0.0);
            weights[i][k] = w;
        }
        // Slaney area normalization
        let enorm = 2.0 / (mel_f[i + 2] - mel_f[i]);
        for k in 0..N_BINS {
            weights[i][k] *= enorm;
        }
    }
    weights
}

/// `librosa.power_to_db(S)` with defaults ref=1.0, amin=1e-10, top_db=80.
fn power_to_db(mut mel: Vec<Vec<f64>>) -> Vec<Vec<f64>> {
    let amin = 1e-10_f64;
    let mut max_db = f64::NEG_INFINITY;
    for row in &mut mel {
        for v in row.iter_mut() {
            *v = 10.0 * v.max(amin).log10(); // ref=1.0 → -10*log10(1)=0
            if *v > max_db {
                max_db = *v;
            }
        }
    }
    let floor = max_db - 80.0;
    for row in &mut mel {
        for v in row.iter_mut() {
            if *v < floor {
                *v = floor;
            }
        }
    }
    mel
}

/// Spectral-flux onset strength envelope (mean aggregate, lag=1, max_size=1),
/// with librosa's center compensation. Returns a vector of length `n_frames`.
fn onset_strength(samples: &[f64], sample_rate: u32) -> Option<Vec<f64>> {
    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(N_FFT);

    let power = stft_power(samples, &fft);
    let n_frames = power.len();
    if n_frames < 2 {
        return None;
    }

    let mel_basis = mel_filterbank(sample_rate);
    // melspec[m][t] = Σ_f mel_basis[m][f] * power[t][f]
    let mut mel = vec![vec![0.0_f64; n_frames]; N_MELS];
    for (t, col) in power.iter().enumerate() {
        for m in 0..N_MELS {
            let mb = &mel_basis[m];
            let mut acc = 0.0;
            for f in 0..N_BINS {
                acc += mb[f] * col[f];
            }
            mel[m][t] = acc;
        }
    }
    let db = power_to_db(mel);

    // Spectral flux: mean_f max(0, db[f,t] - db[f,t-1]); length n_frames-1
    let mut flux = vec![0.0_f64; n_frames - 1];
    for t in 1..n_frames {
        let mut acc = 0.0;
        for m in 0..N_MELS {
            let d = db[m][t] - db[m][t - 1];
            if d > 0.0 {
                acc += d;
            }
        }
        flux[t - 1] = acc / N_MELS as f64;
    }

    // Pad front by lag + n_fft/(2*hop) = 1 + 2 = 3, then trim to n_frames.
    let pad_width = 1 + N_FFT / (2 * HOP);
    let mut env = vec![0.0_f64; pad_width + flux.len()];
    env[pad_width..].copy_from_slice(&flux);
    env.truncate(n_frames);
    Some(env)
}

// ---------------------------------------------------------------------------
// Tempo estimation (tempogram + log-normal prior)
// ---------------------------------------------------------------------------

/// Bounded-lag autocorrelation of `x` for lags 0..`max_lag` via FFT power
/// spectrum (linear, zero-padded). Constant scale factors are irrelevant —
/// callers normalize. `fft`/`ifft` operate on `n_pad` ≥ 2*len-1.
fn autocorrelate(x: &[f64], max_lag: usize) -> Vec<f64> {
    let n = x.len();
    let need = 2 * n - 1;
    let mut n_pad = 1;
    while n_pad < need {
        n_pad <<= 1;
    }
    let mut planner = FftPlanner::new();
    let fwd = planner.plan_fft_forward(n_pad);
    let inv = planner.plan_fft_inverse(n_pad);
    let mut buf = vec![Complex { re: 0.0, im: 0.0 }; n_pad];
    for (i, &v) in x.iter().enumerate() {
        buf[i].re = v;
    }
    fwd.process(&mut buf);
    for c in buf.iter_mut() {
        let p = c.re * c.re + c.im * c.im;
        c.re = p;
        c.im = 0.0;
    }
    inv.process(&mut buf);
    (0..max_lag.min(n_pad)).map(|i| buf[i].re).collect()
}

/// Estimate global tempo (BPM) from the onset envelope, mirroring
/// `librosa.feature.tempo` (default prior, start_bpm=120, std_bpm=1, max_tempo=320).
fn estimate_tempo(onset_env: &[f64], sample_rate: u32) -> f64 {
    let n = onset_env.len();
    if n < 2 {
        return 0.0;
    }
    // Tempogram: centered, linear-ramp padded, framed, Hann-windowed,
    // autocorrelated, l-inf normalized per frame; then mean over time.
    let half = TG_WIN / 2;
    let mut padded = vec![0.0_f64; n + 2 * half];
    // linear_ramp front: 0 → onset[0]
    let edge0 = onset_env[0];
    for i in 0..half {
        padded[i] = edge0 * (i as f64 / half as f64);
    }
    padded[half..half + n].copy_from_slice(onset_env);
    // linear_ramp back: onset[-1] → 0
    let edge1 = onset_env[n - 1];
    for i in 0..half {
        padded[half + n + i] = edge1 + (0.0 - edge1) * ((i + 1) as f64 / half as f64);
    }

    let ac_window = hann_periodic(TG_WIN);
    // Aggregate (mean over the n frames) of the per-frame normalized autocorr.
    let mut tg_mean = vec![0.0_f64; TG_WIN];
    let mut frame = vec![0.0_f64; TG_WIN];
    for j in 0..n {
        for k in 0..TG_WIN {
            frame[k] = padded[j + k] * ac_window[k];
        }
        let ac = autocorrelate(&frame, TG_WIN);
        let maxabs = ac.iter().cloned().fold(0.0_f64, |a, b| a.max(b.abs()));
        if maxabs > 0.0 {
            for k in 0..TG_WIN {
                tg_mean[k] += ac[k] / maxabs;
            }
        }
    }
    for v in tg_mean.iter_mut() {
        *v /= n as f64;
    }

    // BPM per lag bin; bin 0 is 0-lag (∞ BPM).
    let sr = sample_rate as f64;
    let start_bpm = 120.0_f64;
    let std_bpm = 1.0_f64;
    let max_tempo = 320.0_f64;
    let mut best_period = 0usize;
    let mut best_score = f64::NEG_INFINITY;
    for lag in 1..TG_WIN {
        let bpm = 60.0 * sr / (HOP as f64 * lag as f64);
        if bpm >= max_tempo {
            continue; // logprior = -inf for bpm >= max_tempo
        }
        let logprior = -0.5 * ((bpm.log2() - start_bpm.log2()) / std_bpm).powi(2);
        let score = (1.0 + 1e6 * tg_mean[lag]).ln() + logprior; // log1p(1e6*tg)
        if score > best_score {
            best_score = score;
            best_period = lag;
        }
    }
    if best_period == 0 {
        return 0.0;
    }
    60.0 * sr / (HOP as f64 * best_period as f64)
}

// ---------------------------------------------------------------------------
// Dynamic-programming beat tracker (Ellis 2007)
// ---------------------------------------------------------------------------

/// Track beats from the onset envelope at the given tempo, mirroring librosa's
/// `__beat_tracker` (tightness=100, trim=True). Returns beat frame indices.
fn beat_track(onset_env: &[f64], bpm: f64, sample_rate: u32) -> Vec<usize> {
    let n = onset_env.len();
    if n == 0 || !(bpm > 0.0) {
        return Vec::new();
    }
    let frame_rate = sample_rate as f64 / HOP as f64;
    let fpb = (frame_rate * 60.0 / bpm).round();
    if fpb < 1.0 {
        return Vec::new();
    }
    let fpb_i = fpb as i64;

    // Normalize onsets by std (ddof=1).
    let mean = onset_env.iter().sum::<f64>() / n as f64;
    let var = if n > 1 {
        onset_env.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (n as f64 - 1.0)
    } else {
        0.0
    };
    let norm = var.sqrt() + f64::MIN_POSITIVE;
    let normed: Vec<f64> = onset_env.iter().map(|&x| x / norm).collect();

    // Local score: Gaussian-weighted same-mode convolution.
    // window[k] = exp(-0.5 * ((k - fpb) * 32 / fpb)^2), k = 0..2*fpb
    let k_len = (2 * fpb_i + 1) as usize;
    let window: Vec<f64> = (0..k_len)
        .map(|k| {
            let x = (k as f64 - fpb) * 32.0 / fpb;
            (-0.5 * x * x).exp()
        })
        .collect();
    let half_k = k_len / 2;
    let mut localscore = vec![0.0_f64; n];
    for i in 0..n {
        let mut acc = 0.0;
        let lo = if i + half_k + 1 > n { i + half_k + 1 - n } else { 0 };
        let hi = (i + half_k + 1).min(k_len);
        for k in lo..hi {
            acc += window[k] * normed[i + half_k - k];
        }
        localscore[i] = acc;
    }

    // DP.
    let tightness = 100.0_f64;
    let score_thresh = 0.01 * localscore.iter().cloned().fold(0.0_f64, f64::max);
    let mut backlink = vec![-1_i64; n];
    let mut cumscore = vec![0.0_f64; n];
    let mut first_beat = true;
    let log_fpb = fpb.ln();
    for i in 0..n {
        let score_i = localscore[i];
        let mut best_score = f64::NEG_INFINITY;
        let mut beat_location: i64 = -1;
        // loc in range(i - round(fpb/2), i - 2*fpb - 1, -1)
        let loc_start = i as i64 - (fpb / 2.0).round() as i64;
        let loc_stop = i as i64 - 2 * fpb_i - 1; // exclusive
        let mut loc = loc_start;
        while loc > loc_stop {
            if loc < 0 {
                break;
            }
            let interval = (i as i64 - loc) as f64;
            let score = cumscore[loc as usize]
                - tightness * (interval.ln() - log_fpb).powi(2);
            if score > best_score {
                best_score = score;
                beat_location = loc;
            }
            loc -= 1;
        }
        cumscore[i] = if beat_location >= 0 {
            score_i + best_score
        } else {
            score_i
        };
        if first_beat && score_i < score_thresh {
            backlink[i] = -1;
        } else {
            backlink[i] = beat_location;
            first_beat = false;
        }
    }

    // Last beat: localmax(cumscore), threshold = 0.5 * median(cumscore[localmax]).
    let localmax = local_max(&cumscore);
    let mut peak_vals: Vec<f64> = (0..n).filter(|&i| localmax[i]).map(|i| cumscore[i]).collect();
    let threshold = if peak_vals.is_empty() {
        0.0
    } else {
        0.5 * median(&mut peak_vals)
    };
    let mut tail: i64 = (n - 1) as i64;
    let mut m = (n - 1) as i64;
    while m >= 0 {
        if localmax[m as usize] && cumscore[m as usize] >= threshold {
            tail = m;
            break;
        }
        m -= 1;
    }

    // Backtrack.
    let mut beats_bool = vec![false; n];
    let mut node = tail;
    while node >= 0 {
        beats_bool[node as usize] = true;
        node = backlink[node as usize];
    }

    // Trim spurious leading/trailing beats below 1/2 RMS of smoothed beat env.
    trim_beats(&localscore, &mut beats_bool);

    (0..n).filter(|&i| beats_bool[i]).collect()
}

/// `librosa.util.localmax`: x[i] > x[i-1] && x[i] >= x[i+1] (x[0] never max).
fn local_max(x: &[f64]) -> Vec<bool> {
    let n = x.len();
    let mut m = vec![false; n];
    for i in 1..n {
        let right = if i + 1 < n { x[i] >= x[i + 1] } else { x[i] > x[i - 1] };
        m[i] = x[i] > x[i - 1] && right;
    }
    if n >= 2 {
        m[n - 1] = x[n - 1] > x[n - 2];
    }
    m
}

fn median(v: &mut [f64]) -> f64 {
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = v.len();
    if n == 0 {
        0.0
    } else if n % 2 == 1 {
        v[n / 2]
    } else {
        0.5 * (v[n / 2 - 1] + v[n / 2])
    }
}

/// Mirror `__trim_beats`: remove leading/trailing beats whose localscore is at
/// or below 1/2 the RMS of the Hann-smoothed beat envelope.
fn trim_beats(localscore: &[f64], beats: &mut [bool]) {
    let n = localscore.len();
    let beat_idx: Vec<usize> = (0..n).filter(|&i| beats[i]).collect();
    if beat_idx.is_empty() {
        return;
    }
    // smooth_boe = convolve(localscore[beats], hanning(5))[2:]  (numpy hanning: symmetric)
    let w = [0.0_f64, 0.5, 1.0, 0.5, 0.0]; // np.hanning(5)
    let boe: Vec<f64> = beat_idx.iter().map(|&i| localscore[i]).collect();
    let conv_len = boe.len() + w.len() - 1;
    let mut conv = vec![0.0_f64; conv_len];
    for (a, &bv) in boe.iter().enumerate() {
        for (b, &wv) in w.iter().enumerate() {
            conv[a + b] += bv * wv;
        }
    }
    let smooth: &[f64] = &conv[(w.len() / 2)..]; // [2:]
    let threshold = if smooth.is_empty() {
        0.0
    } else {
        0.5 * (smooth.iter().map(|x| x * x).sum::<f64>() / smooth.len() as f64).sqrt()
    };

    // Suppress leading frames with weak localscore.
    let mut i = 0;
    while i < n && localscore[i] <= threshold {
        beats[i] = false;
        i += 1;
    }
    // Suppress trailing frames with weak localscore.
    let mut j = n as i64 - 1;
    while j >= 0 && localscore[j as usize] <= threshold {
        beats[j as usize] = false;
        j -= 1;
    }
}

/// Per-frame RMS, `librosa.feature.rms` defaults: frame_length=2048, hop=512,
/// center=True with constant (zero) padding of frame_length//2.
fn framed_rms(samples: &[f64]) -> Vec<f64> {
    let frame_length = 2048usize;
    let hop = 512usize;
    let pad = frame_length / 2;
    let mut y = vec![0.0_f64; samples.len() + 2 * pad];
    y[pad..pad + samples.len()].copy_from_slice(samples);
    if y.len() < frame_length {
        return Vec::new();
    }
    let n_frames = 1 + (y.len() - frame_length) / hop;
    let mut out = Vec::with_capacity(n_frames);
    for t in 0..n_frames {
        let start = t * hop;
        let s: f64 = y[start..start + frame_length].iter().map(|v| v * v).sum();
        out.push((s / frame_length as f64).sqrt());
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Deterministic click train: decaying 1 kHz bursts every 60/bpm seconds.
    /// Mirrors the Python fixture generator so values can be compared directly.
    fn click_train(bpm: f64, dur: f64, sr: u32) -> Vec<f64> {
        let n = (dur * sr as f64) as usize;
        let mut y = vec![0.0_f64; n];
        let burst_len = (0.05 * sr as f64) as usize;
        let burst: Vec<f64> = (0..burst_len)
            .map(|i| {
                let t = i as f64 / sr as f64;
                (2.0 * PI * 1000.0 * t).sin() * (-40.0 * t).exp()
            })
            .collect();
        let period = 60.0 / bpm;
        let mut k = 0;
        loop {
            let idx = (k as f64 * period * sr as f64) as usize;
            if idx + burst_len >= n {
                break;
            }
            for i in 0..burst_len {
                y[idx + i] += burst[i];
            }
            k += 1;
        }
        y
    }

    #[test]
    fn silence_ratio_matches_python() {
        // Cross-path parity vs the Python fallback (librosa 0.11.0,
        // TemporalOperations.calculate_silence_ratio). Tight tolerance: the
        // ported framing reproduces librosa to ~1e-4.
        let y120 = click_train(120.0, 10.0, 44100);
        assert!((silence_ratio(&y120) - 0.810905).abs() < 1e-3);

        let y90 = click_train(90.0, 10.0, 44100);
        assert!((silence_ratio(&y90) - 0.857309).abs() < 1e-3);
    }

    #[test]
    fn rhythm_stability_matches_python() {
        // Cross-path parity vs the Python fallback
        // (calculate_rhythm_stability → beat_track). The full librosa beat
        // tracker reproduces the reference to ~1e-4 on steady click trains.
        let y120 = click_train(120.0, 10.0, 44100);
        assert!((rhythm_stability(&y120, 44100) - 0.994708).abs() < 1e-3);

        let y90 = click_train(90.0, 10.0, 44100);
        assert!((rhythm_stability(&y90, 44100) - 0.991593).abs() < 1e-3);
    }

    /// Deterministic alternating-interval train (no RNG): periods alternate
    /// 0.5 s / 0.66 s. Reproduces the Python fixture exactly.
    fn alternating_train(dur: f64, sr: u32, p_a: f64, p_b: f64) -> Vec<f64> {
        let n = (dur * sr as f64) as usize;
        let mut y = vec![0.0_f64; n];
        let burst_len = (0.05 * sr as f64) as usize;
        let burst: Vec<f64> = (0..burst_len)
            .map(|i| {
                let t = i as f64 / sr as f64;
                (2.0 * PI * 1000.0 * t).sin() * (-40.0 * t).exp()
            })
            .collect();
        let mut pos = 0.0_f64;
        let mut k = 0usize;
        loop {
            let idx = (pos * sr as f64) as usize;
            if idx + burst_len >= n {
                break;
            }
            for i in 0..burst_len {
                y[idx + i] += burst[i];
            }
            pos += if k % 2 == 0 { p_a } else { p_b };
            k += 1;
        }
        y
    }

    #[test]
    fn rhythm_stability_discriminates_irregular() {
        // Irregular rhythm must score lower than a steady one, and match the
        // Python reference (0.886054) — proving the metric is meaningful, not
        // a constant. Steady 120 BPM → 0.9947.
        let y = alternating_train(12.0, 44100, 0.5, 0.66);
        let rs = rhythm_stability(&y, 44100);
        assert!((rs - 0.886054).abs() < 5e-3, "irregular rhythm_stability={rs}");
        assert!(rs < 0.95, "irregular ({rs}) should score below steady (~0.995)");
    }

    #[test]
    fn tempo_estimate_near_120() {
        let y = click_train(120.0, 10.0, 44100);
        let env = onset_strength(&y, 44100).expect("onset env");
        let bpm = estimate_tempo(&env, 44100);
        // Python tempo for this fixture ≈ 120.185 BPM.
        assert!((bpm - 120.0).abs() < 6.0, "tempo={bpm}");
    }

    #[test]
    fn silence_ratio_all_silent() {
        assert_eq!(silence_ratio(&vec![0.0; 44100]), 1.0);
    }

    #[test]
    fn mel_filterbank_checksum() {
        // Python: librosa.filters.mel(sr=44100, n_fft=2048, n_mels=128)
        //   sum ≈ 5.94156, max ≈ 0.0321513
        let mb = mel_filterbank(44100);
        let sum: f64 = mb.iter().flat_map(|r| r.iter()).sum();
        let max = mb.iter().flat_map(|r| r.iter()).cloned().fold(0.0_f64, f64::max);
        assert!((sum - 5.94156).abs() < 0.01, "mel sum={sum}");
        assert!((max - 0.0321513).abs() < 1e-4, "mel max={max}");
    }
}
