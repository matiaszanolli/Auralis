"""
Processing Logger
~~~~~~~~~~~~~~~~~

Unified logging for processing steps.
Consolidates 41+ duplicate print/debug statement patterns across modes.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""



class ProcessingLogger:
    """
    Unified logging for processing steps.
    Consolidates 41+ duplicate print/debug statement patterns across modes.
    """

    @staticmethod
    def pre_stage(stage_name: str, peak_db: float, rms_db: float, crest_db: float | None = None) -> None:
        """Log measurements before a processing stage."""
        if crest_db is not None:
            print(f"[{stage_name}] Peak: {peak_db:.2f} dB, RMS: {rms_db:.2f} dB, Crest: {crest_db:.2f} dB")
        else:
            print(f"[{stage_name}] Peak: {peak_db:.2f} dB, LUFS: {rms_db:.1f}")

    @staticmethod
    def post_stage(stage_name: str, before_db: float, after_db: float, metric_type: str = "Peak") -> None:
        """Log measurement change after a processing stage."""
        delta = after_db - before_db
        print(f"[{stage_name}] {metric_type}: {before_db:.2f} → {after_db:.2f} dB (change: {delta:+.2f} dB)")

    @staticmethod
    def safety_check(reason: str, peak_db: float | None = None) -> None:
        """Log safety check decisions."""
        if peak_db is not None:
            print(f"[{reason}] Peak {peak_db:.2f} dB")
        else:
            print(f"[{reason}]")

    @staticmethod
    def stereo_width_change(stage_name: str, before_width: float, after_width: float,
                           before_peak_db: float | None = None, after_peak_db: float | None = None) -> None:
        """Log stereo width adjustments."""
        if before_peak_db is not None and after_peak_db is not None:
            print(f"[{stage_name}] Peak: {before_peak_db:.2f} → {after_peak_db:.2f} dB "
                  f"(width: {before_width:.2f} → {after_width:.2f})")
        else:
            print(f"[{stage_name}] {before_width:.2f} → {after_width:.2f} (target: {after_width:.2f})")

    @staticmethod
    def gain_applied(stage_name: str, gain_db: float, target_db: float | None = None) -> None:
        """Log gain/boost application."""
        if target_db is not None:
            print(f"[{stage_name}] Applied {gain_db:+.2f} dB (target: {target_db:.1f} dB)")
        else:
            print(f"[{stage_name}] Applied {gain_db:+.2f} dB")

    @staticmethod
    def skipped(reason: str, detail: str | None = None) -> None:
        """Log when an operation is skipped."""
        if detail:
            print(f"[{reason}] SKIPPED - {detail}")
        else:
            print(f"[{reason}] SKIPPED")

    @staticmethod
    def limited(reason: str, original: float, limited: float) -> None:
        """Log when a value is limited/clamped."""
        print(f"[{reason}] Limited: {original:.2f} → {limited:.2f}")
