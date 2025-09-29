# Real-time Adaptive Processing Pipeline Design

## Overview

This document details the design of a real-time adaptive audio processing pipeline that replaces reference-based mastering with intelligent, content-aware processing optimized for the Auralis media player.

## Pipeline Architecture

### High-Level Flow
```
Audio Input → Content Analysis → Target Generation → Adaptive Processing → Quality Monitoring → Audio Output
     ↓              ↓                ↓                    ↓                   ↓               ↓
  20ms chunks   Genre/Style     Optimal Targets    Real-time DSP        Feedback Loop    Enhanced Audio
```

### Latency Budget (Target: <20ms total)
- **Content Analysis**: 4ms
- **Target Generation**: 2ms
- **Adaptive Processing**: 12ms
- **Quality Monitoring**: 2ms
- **Total**: 20ms

## Component Design

### 1. Content Analysis Engine (4ms budget)

```python
class RealtimeContentAnalyzer:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.chunk_size = int(0.02 * sample_rate)  # 20ms chunks

        # Efficient analysis models
        self.genre_classifier = LightweightGenreClassifier()
        self.energy_analyzer = EnergyProfileAnalyzer()
        self.spectral_analyzer = FastSpectralAnalyzer()
        self.temporal_analyzer = TemporalFeatureExtractor()

        # Analysis history for context
        self.analysis_history = CircularBuffer(size=50)  # 1 second history
        self.current_profile = ContentProfile()

    def analyze_chunk(self, audio_chunk: np.ndarray) -> ContentFeatures:
        """
        Analyze 20ms audio chunk for content characteristics
        Target: <4ms processing time
        """
        features = ContentFeatures()

        # Fast spectral analysis (1.5ms)
        spectrum = self.spectral_analyzer.compute_spectrum(audio_chunk)
        features.spectral_centroid = np.mean(spectrum * self.spectral_analyzer.freq_bins) / np.sum(spectrum)
        features.spectral_rolloff = self.calculate_spectral_rolloff(spectrum)
        features.spectral_flux = self.calculate_spectral_flux(spectrum)

        # Energy analysis (1ms)
        features.rms_energy = np.sqrt(np.mean(audio_chunk**2))
        features.peak_energy = np.max(np.abs(audio_chunk))
        features.zero_crossing_rate = self.calculate_zcr(audio_chunk)

        # Temporal features (1ms)
        features.attack_time = self.estimate_attack_time(audio_chunk)
        features.crest_factor = features.peak_energy / (features.rms_energy + 1e-10)

        # Genre hints (0.5ms - lightweight classification)
        features.genre_hints = self.genre_classifier.quick_classify(spectrum)

        # Update history and profile
        self.analysis_history.append(features)
        self.update_content_profile(features)

        return features

    def update_content_profile(self, features: ContentFeatures):
        """Update long-term content understanding"""
        # Exponential moving average for stability
        alpha = 0.1  # Adaptation rate

        self.current_profile.avg_spectral_centroid = (
            alpha * features.spectral_centroid +
            (1 - alpha) * self.current_profile.avg_spectral_centroid
        )

        self.current_profile.avg_energy = (
            alpha * features.rms_energy +
            (1 - alpha) * self.current_profile.avg_energy
        )

        # Update genre confidence over time
        self.current_profile.update_genre_confidence(features.genre_hints)
```

### 2. Adaptive Target Generator (2ms budget)

```python
class AdaptiveTargetGenerator:
    def __init__(self):
        self.genre_profiles = self.load_genre_profiles()
        self.psychoacoustic_model = PsychoacousticModel()
        self.user_preferences = UserPreferencesManager()

    def generate_targets(self, content_features: ContentFeatures,
                        content_profile: ContentProfile) -> ProcessingTargets:
        """
        Generate optimal processing targets based on content analysis
        Target: <2ms processing time
        """
        targets = ProcessingTargets()

        # Get base profile for detected genre (0.5ms)
        base_profile = self.get_genre_profile(content_profile.primary_genre)

        # Adapt based on content characteristics (1ms)
        targets.target_lufs = self.calculate_adaptive_lufs(
            base_profile.target_lufs,
            content_features.rms_energy,
            content_profile.avg_energy
        )

        targets.eq_targets = self.calculate_adaptive_eq_targets(
            base_profile.eq_curve,
            content_features.spectral_centroid,
            content_features.spectral_rolloff
        )

        targets.dynamics_targets = self.calculate_dynamics_targets(
            base_profile.compression_ratio,
            content_features.crest_factor,
            content_features.attack_time
        )

        # Apply user preferences (0.5ms)
        targets = self.apply_user_preferences(targets)

        return targets

    def calculate_adaptive_lufs(self, base_lufs: float, current_energy: float,
                               avg_energy: float) -> float:
        """Calculate adaptive LUFS target based on content energy"""
        energy_ratio = current_energy / (avg_energy + 1e-10)

        # Adjust target based on local energy variations
        if energy_ratio > 1.5:  # High energy section
            return base_lufs + 1.0  # Allow slightly louder
        elif energy_ratio < 0.7:  # Low energy section
            return base_lufs - 1.0  # Keep quieter sections natural
        else:
            return base_lufs

    def calculate_adaptive_eq_targets(self, base_curve: np.ndarray,
                                     spectral_centroid: float,
                                     spectral_rolloff: float) -> np.ndarray:
        """Calculate adaptive EQ curve based on spectral characteristics"""
        eq_curve = base_curve.copy()

        # Adapt based on spectral centroid
        if spectral_centroid > 3000:  # Bright content
            eq_curve[self.get_freq_index(2000):self.get_freq_index(8000)] -= 1.0
        elif spectral_centroid < 1000:  # Dark content
            eq_curve[self.get_freq_index(2000):self.get_freq_index(8000)] += 2.0

        # Adapt based on spectral rolloff
        rolloff_index = self.get_freq_index(spectral_rolloff)
        eq_curve[rolloff_index:] *= 0.8  # Gentle high-frequency adjustment

        return eq_curve
```

### 3. Real-time Adaptive Processor (12ms budget)

```python
class RealtimeAdaptiveProcessor:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate

        # Processing modules with optimized algorithms
        self.adaptive_eq = PsychoacousticEQ(sample_rate)
        self.adaptive_compressor = AdaptiveCompressor(sample_rate)
        self.adaptive_limiter = AdaptiveLimiter(sample_rate)
        self.stereo_processor = StereoWidthProcessor(sample_rate)

        # Processing state
        self.current_targets = ProcessingTargets()
        self.smoothing_coefficients = SmoothingCoefficients()

    def process_chunk(self, audio_chunk: np.ndarray,
                     targets: ProcessingTargets) -> np.ndarray:
        """
        Apply adaptive processing to audio chunk
        Target: <12ms processing time
        """
        # Smooth target transitions to avoid artifacts (1ms)
        smoothed_targets = self.smooth_target_transitions(targets)

        # Stage 1: Adaptive EQ (4ms)
        processed_audio = self.adaptive_eq.process(
            audio_chunk,
            smoothed_targets.eq_targets
        )

        # Stage 2: Adaptive Dynamics (4ms)
        processed_audio = self.adaptive_compressor.process(
            processed_audio,
            smoothed_targets.dynamics_targets
        )

        # Stage 3: Stereo Processing (2ms)
        if processed_audio.ndim == 2:  # Stereo
            processed_audio = self.stereo_processor.process(
                processed_audio,
                smoothed_targets.stereo_width
            )

        # Stage 4: Adaptive Limiting (1ms)
        processed_audio = self.adaptive_limiter.process(
            processed_audio,
            smoothed_targets.target_lufs
        )

        return processed_audio

    def smooth_target_transitions(self, new_targets: ProcessingTargets) -> ProcessingTargets:
        """Smooth parameter changes to avoid audio artifacts"""
        smoothed = ProcessingTargets()
        alpha = 0.1  # Smoothing factor

        # Smooth EQ transitions
        smoothed.eq_targets = (
            alpha * new_targets.eq_targets +
            (1 - alpha) * self.current_targets.eq_targets
        )

        # Smooth dynamics parameters
        smoothed.dynamics_targets = self.smooth_dynamics_parameters(
            new_targets.dynamics_targets,
            self.current_targets.dynamics_targets,
            alpha
        )

        # Update current targets
        self.current_targets = smoothed

        return smoothed
```

### 4. Psychoacoustic EQ Implementation

```python
class PsychoacousticEQ:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate

        # Critical bands based on Bark scale (26 bands)
        self.critical_bands = self.generate_critical_bands()
        self.band_filters = self.create_band_filters()

        # Psychoacoustic masking model
        self.masking_model = MaskingThresholdCalculator()

    def process(self, audio_chunk: np.ndarray, eq_targets: np.ndarray) -> np.ndarray:
        """
        Apply psychoacoustic-based adaptive EQ
        Target: <4ms processing time
        """
        # Analyze current spectrum (1ms)
        current_spectrum = np.fft.rfft(audio_chunk, axis=0)

        # Calculate masking thresholds (1ms)
        masking_thresholds = self.masking_model.calculate_thresholds(current_spectrum)

        # Apply adaptive filtering (2ms)
        processed_spectrum = self.apply_adaptive_filters(
            current_spectrum,
            eq_targets,
            masking_thresholds
        )

        # Convert back to time domain
        processed_audio = np.fft.irfft(processed_spectrum, axis=0)

        return processed_audio

    def apply_adaptive_filters(self, spectrum: np.ndarray,
                              eq_targets: np.ndarray,
                              masking_thresholds: np.ndarray) -> np.ndarray:
        """Apply frequency-domain filtering with masking awareness"""
        processed_spectrum = spectrum.copy()

        for band_idx, (low_freq, high_freq) in enumerate(self.critical_bands):
            # Get frequency indices for this band
            low_idx = int(low_freq * len(spectrum) / (self.sample_rate / 2))
            high_idx = int(high_freq * len(spectrum) / (self.sample_rate / 2))

            # Calculate adaptive gain for this band
            current_energy = np.mean(np.abs(spectrum[low_idx:high_idx])**2)
            masking_threshold = masking_thresholds[band_idx]
            target_gain = eq_targets[band_idx]

            # Apply masking-aware gain adjustment
            if current_energy > masking_threshold:
                adaptive_gain = target_gain
            else:
                # Reduce gain when below masking threshold
                adaptive_gain = target_gain * 0.5

            # Apply gain to frequency band
            processed_spectrum[low_idx:high_idx] *= adaptive_gain

        return processed_spectrum
```

### 5. Adaptive Dynamics Processor

```python
class AdaptiveCompressor:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.envelope_follower = EnvelopeFollower(sample_rate)
        self.gain_computer = AdaptiveGainComputer()

        # State variables for smooth operation
        self.previous_gain = 1.0
        self.envelope_history = CircularBuffer(size=1024)

    def process(self, audio_chunk: np.ndarray,
               dynamics_targets: DynamicsTargets) -> np.ndarray:
        """
        Apply adaptive dynamics processing
        Target: <4ms processing time
        """
        # Track envelope (1ms)
        envelope = self.envelope_follower.process(audio_chunk)

        # Compute adaptive gain reduction (2ms)
        gain_reduction = self.gain_computer.compute_gain(
            envelope,
            dynamics_targets,
            self.envelope_history
        )

        # Smooth gain transitions (0.5ms)
        smoothed_gain = self.smooth_gain_reduction(gain_reduction)

        # Apply gain reduction (0.5ms)
        processed_audio = audio_chunk * smoothed_gain

        # Update history
        self.envelope_history.append(envelope)
        self.previous_gain = smoothed_gain[-1]

        return processed_audio

    def smooth_gain_reduction(self, gain_reduction: np.ndarray) -> np.ndarray:
        """Smooth gain changes to prevent artifacts"""
        smoothed_gain = np.zeros_like(gain_reduction)
        smoothed_gain[0] = 0.9 * self.previous_gain + 0.1 * gain_reduction[0]

        # Apply time constants for attack/release
        attack_coeff = np.exp(-1.0 / (0.003 * self.sample_rate))  # 3ms attack
        release_coeff = np.exp(-1.0 / (0.1 * self.sample_rate))   # 100ms release

        for i in range(1, len(gain_reduction)):
            if gain_reduction[i] < smoothed_gain[i-1]:  # Attack
                smoothed_gain[i] = (attack_coeff * smoothed_gain[i-1] +
                                   (1 - attack_coeff) * gain_reduction[i])
            else:  # Release
                smoothed_gain[i] = (release_coeff * smoothed_gain[i-1] +
                                   (1 - release_coeff) * gain_reduction[i])

        return smoothed_gain
```

### 6. Quality Monitoring and Feedback (2ms budget)

```python
class RealtimeQualityMonitor:
    def __init__(self):
        self.quality_history = CircularBuffer(size=100)  # 2 second history
        self.distortion_detector = RealtimeDistortionDetector()
        self.loudness_tracker = RealtimeLoudnessTracker()

    def monitor_chunk(self, original_chunk: np.ndarray,
                     processed_chunk: np.ndarray) -> QualityFeedback:
        """
        Monitor processing quality and provide feedback
        Target: <2ms processing time
        """
        feedback = QualityFeedback()

        # Quick distortion check (0.5ms)
        feedback.distortion_level = self.distortion_detector.detect(processed_chunk)

        # Loudness tracking (0.5ms)
        feedback.current_lufs = self.loudness_tracker.update(processed_chunk)

        # Quality trend analysis (1ms)
        feedback.quality_trend = self.analyze_quality_trend()

        # Generate adaptive feedback for next chunk
        feedback.processing_adjustments = self.generate_adjustments(feedback)

        self.quality_history.append(feedback)

        return feedback

    def generate_adjustments(self, feedback: QualityFeedback) -> ProcessingAdjustments:
        """Generate processing adjustments based on quality feedback"""
        adjustments = ProcessingAdjustments()

        # Adjust processing intensity based on distortion
        if feedback.distortion_level > 0.01:  # 1% THD threshold
            adjustments.reduce_processing_intensity = True
            adjustments.intensity_reduction = 0.8

        # Adjust loudness targeting
        if abs(feedback.current_lufs - feedback.target_lufs) > 2.0:
            adjustments.loudness_correction = (
                feedback.target_lufs - feedback.current_lufs
            ) * 0.1  # Gentle correction

        return adjustments
```

### 7. Complete Pipeline Integration

```python
class AdaptiveProcessingPipeline:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.chunk_size = int(0.02 * sample_rate)  # 20ms chunks

        # Initialize all components
        self.content_analyzer = RealtimeContentAnalyzer(sample_rate)
        self.target_generator = AdaptiveTargetGenerator()
        self.processor = RealtimeAdaptiveProcessor(sample_rate)
        self.quality_monitor = RealtimeQualityMonitor()

        # Performance monitoring
        self.performance_tracker = PerformanceTracker()

    def process_audio_stream(self, audio_stream):
        """
        Process continuous audio stream with adaptive mastering
        """
        for chunk in audio_stream.chunks(self.chunk_size):
            start_time = time.perf_counter()

            # Step 1: Analyze content (4ms)
            content_features = self.content_analyzer.analyze_chunk(chunk)

            # Step 2: Generate targets (2ms)
            targets = self.target_generator.generate_targets(
                content_features,
                self.content_analyzer.current_profile
            )

            # Step 3: Process audio (12ms)
            processed_chunk = self.processor.process_chunk(chunk, targets)

            # Step 4: Monitor quality (2ms)
            quality_feedback = self.quality_monitor.monitor_chunk(
                chunk, processed_chunk
            )

            # Apply any necessary adjustments
            if quality_feedback.processing_adjustments:
                self.apply_quality_adjustments(quality_feedback.processing_adjustments)

            # Track performance
            processing_time = (time.perf_counter() - start_time) * 1000
            self.performance_tracker.record_timing(processing_time)

            yield processed_chunk

    def apply_quality_adjustments(self, adjustments: ProcessingAdjustments):
        """Apply real-time adjustments based on quality feedback"""
        if adjustments.reduce_processing_intensity:
            self.processor.reduce_intensity(adjustments.intensity_reduction)

        if adjustments.loudness_correction:
            self.processor.adjust_loudness_target(adjustments.loudness_correction)
```

## Performance Optimization Strategies

### 1. Algorithm Optimization
- **FFT Optimization**: Use optimized FFT libraries (FFTW)
- **SIMD Instructions**: Vectorized operations for critical paths
- **Memory Management**: Pre-allocated buffers, circular buffers
- **Cache Optimization**: Data structure alignment for cache efficiency

### 2. Real-time Considerations
- **Thread Priority**: High-priority audio thread
- **Memory Allocation**: No dynamic allocation in audio thread
- **Error Handling**: Graceful degradation instead of failures
- **Fallback Modes**: Simplified processing for performance constraints

### 3. Adaptive Quality Control
```python
class AdaptiveQualityController:
    def __init__(self):
        self.performance_monitor = PerformanceMonitor()
        self.quality_levels = ["maximum", "high", "medium", "basic"]
        self.current_quality = "high"

    def adjust_quality_for_performance(self, processing_time: float):
        """Automatically adjust processing quality based on performance"""
        if processing_time > 18.0:  # Approaching 20ms limit
            if self.current_quality == "maximum":
                self.current_quality = "high"
                self.reduce_fft_size()
            elif self.current_quality == "high":
                self.current_quality = "medium"
                self.reduce_analysis_complexity()
            elif self.current_quality == "medium":
                self.current_quality = "basic"
                self.enable_simplified_mode()
        elif processing_time < 10.0:  # Headroom available
            if self.current_quality != "maximum":
                self.upgrade_quality_level()
```

## Validation and Testing

### Real-time Performance Testing
```python
class PipelineValidator:
    def test_realtime_performance(self, duration_seconds=60):
        """Test pipeline performance over extended period"""
        test_audio = generate_test_audio(duration_seconds, self.sample_rate)

        processing_times = []
        audio_dropouts = 0
        quality_scores = []

        for chunk in test_audio.chunks(self.chunk_size):
            start_time = time.perf_counter()

            try:
                processed_chunk = self.pipeline.process_chunk(chunk)
                processing_time = (time.perf_counter() - start_time) * 1000
                processing_times.append(processing_time)

                if processing_time > 20.0:  # Missed deadline
                    audio_dropouts += 1

            except Exception as e:
                audio_dropouts += 1

        return PerformanceReport(
            avg_processing_time=np.mean(processing_times),
            max_processing_time=np.max(processing_times),
            audio_dropouts=audio_dropouts,
            dropout_rate=audio_dropouts / len(processing_times)
        )
```

## Conclusion

This real-time adaptive processing pipeline design provides a comprehensive framework for intelligent audio mastering that operates within strict latency constraints while delivering professional-quality results. The modular architecture allows for future enhancements and optimizations while maintaining compatibility with existing Auralis systems.

Key innovations include:
- **Psychoacoustic-aware processing** that adapts to human perception
- **Content-aware adaptation** that optimizes for different musical genres and styles
- **Real-time quality monitoring** with automatic adjustment capabilities
- **Performance-adaptive quality control** that maintains reliability under varying system loads

The pipeline is designed to deliver superior results compared to reference-based mastering while requiring no user input, making high-quality audio mastering accessible to all users of the Auralis media player.