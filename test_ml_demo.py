#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ML Genre Classification Demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demonstration of the new ML-based genre classification system
"""

import numpy as np
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

from auralis.analysis.ml_genre_classifier import create_ml_genre_classifier
from auralis.core.hybrid_processor import ContentAnalyzer


def create_test_audio_samples():
    """Create various test audio samples with different characteristics"""

    sample_rate = 44100
    duration = 3.0  # 3 seconds
    t = np.linspace(0, duration, int(sample_rate * duration))

    samples = {}

    # Classical-style: complex harmonics, dynamic range
    classical = (
        0.3 * np.sin(2 * np.pi * 220 * t) +  # A3
        0.2 * np.sin(2 * np.pi * 330 * t) +  # E4
        0.15 * np.sin(2 * np.pi * 440 * t) + # A4
        0.1 * np.sin(2 * np.pi * 660 * t)    # E5
    ) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.2 * t))  # Slow dynamics
    samples['classical'] = classical

    # Electronic-style: synthetic, high frequencies, steady rhythm
    electronic = (
        0.4 * np.sin(2 * np.pi * 880 * t) * (1 + 0.8 * np.sin(2 * np.pi * 8 * t)) +  # High freq modulated
        0.3 * np.sin(2 * np.pi * 110 * t) +  # Sub bass
        0.2 * np.random.randn(len(t)) * (np.sin(2 * np.pi * 4 * t) > 0.5)  # Noise bursts
    )
    samples['electronic'] = electronic

    # Rock-style: mid-heavy, aggressive
    rock = (
        0.4 * np.sin(2 * np.pi * 82 * t) +    # Low E
        0.5 * np.sin(2 * np.pi * 165 * t) +   # Power chord
        0.3 * np.sin(2 * np.pi * 247 * t) +   # Distortion harmonics
        0.2 * np.random.randn(len(t)) * 0.5   # Distortion noise
    ) * (0.8 + 0.2 * np.sin(2 * np.pi * 2 * t))  # Steady rhythm
    samples['rock'] = rock

    # Jazz-style: complex rhythm, varied dynamics
    jazz = (
        0.3 * np.sin(2 * np.pi * 110 * t) +   # Walking bass
        0.25 * np.sin(2 * np.pi * 220 * t) +  # Piano
        0.2 * np.sin(2 * np.pi * 330 * t) +   # Harmony
        0.15 * np.sin(2 * np.pi * 440 * t)    # Melody
    ) * (0.3 + 0.7 * np.abs(np.sin(2 * np.pi * 0.7 * t)))  # Swing feel
    samples['jazz'] = jazz

    return samples


def demonstrate_ml_classification():
    """Demonstrate the ML genre classification system"""

    print("=" * 60)
    print("ML Genre Classification Demo")
    print("=" * 60)

    # Create test samples
    print("Creating test audio samples...")
    samples = create_test_audio_samples()

    # Initialize ML classifier
    print("Initializing ML Genre Classifier...")
    ml_classifier = create_ml_genre_classifier()

    # Show model info
    model_info = ml_classifier.get_model_info()
    print(f"\nModel Info:")
    print(f"  Type: {model_info['model_type']}")
    print(f"  Genres: {', '.join(model_info['genres'])}")
    print(f"  Features: {sum(model_info['feature_count'].values())} total")

    print("\n" + "=" * 60)
    print("Classification Results:")
    print("=" * 60)

    # Test each sample
    for sample_name, audio in samples.items():
        print(f"\nTesting {sample_name.upper()} audio:")
        print("-" * 30)

        # Classify with ML
        result = ml_classifier.classify(audio)

        print(f"  Predicted Genre: {result['primary']}")
        print(f"  Confidence: {result['confidence']:.3f}")

        # Show top 3 probabilities
        sorted_probs = sorted(result['probabilities'].items(),
                            key=lambda x: x[1], reverse=True)[:3]
        print(f"  Top predictions:")
        for genre, prob in sorted_probs:
            print(f"    {genre}: {prob:.3f}")

        # Show feature importance
        importance = result['features_used']
        print(f"  Key features:")
        sorted_features = sorted(importance.items(),
                               key=lambda x: x[1], reverse=True)[:3]
        for feature, weight in sorted_features:
            print(f"    {feature}: {weight:.3f}")


def demonstrate_content_analyzer():
    """Demonstrate the enhanced content analyzer with ML"""

    print("\n" + "=" * 60)
    print("Enhanced Content Analyzer Demo")
    print("=" * 60)

    # Create test samples
    samples = create_test_audio_samples()

    # Initialize content analyzer with ML
    print("Initializing Content Analyzer with ML support...")
    analyzer = ContentAnalyzer(44100, use_ml_classification=True)

    print(f"ML Classification: {'Enabled' if analyzer.use_ml_classification else 'Disabled'}")

    for sample_name, audio in samples.items():
        print(f"\nAnalyzing {sample_name.upper()} audio:")
        print("-" * 30)

        # Analyze content
        profile = analyzer.analyze_content(audio)

        # Show key results
        print(f"  Genre: {profile['genre_info']['primary']}")
        print(f"  Confidence: {profile['genre_info']['confidence']:.3f}")
        print(f"  Energy Level: {profile['energy_level']}")
        print(f"  Dynamic Range: {profile['dynamic_range']:.1f} dB")
        print(f"  Spectral Centroid: {profile['spectral_centroid']:.0f} Hz")
        print(f"  Estimated Tempo: {profile['estimated_tempo']:.0f} BPM")
        print(f"  RMS Level: {profile['rms']:.3f}")


if __name__ == "__main__":
    try:
        demonstrate_ml_classification()
        demonstrate_content_analyzer()

        print("\n" + "=" * 60)
        print("Demo completed successfully!")
        print("The ML genre classification system is working and integrated")
        print("into the adaptive mastering pipeline.")
        print("=" * 60)

    except Exception as e:
        print(f"Demo failed with error: {e}")
        import traceback
        traceback.print_exc()