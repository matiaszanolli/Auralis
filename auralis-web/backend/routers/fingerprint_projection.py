"""Project the stored 25D fingerprint onto the public names and units."""

from collections.abc import Mapping

from auralis.analysis.fingerprint.schema import centroid_to_hz, rolloff_to_hz

_ALIASES = {
    "pitch_stability": "pitch_confidence",
    "chroma_energy": "chroma_energy_mean",
    "phase_correlation": "stereo_correlation",
}
_TO_API_UNITS = {
    "spectral_centroid": centroid_to_hz,
    "spectral_rolloff": rolloff_to_hz,
}


def api_dimension_name(name: str) -> str:
    return _ALIASES.get(name, name.removesuffix("_pct"))


def api_dimension_value(name: str, value: float) -> float:
    convert = _TO_API_UNITS.get(name)
    return value if convert is None else convert(value)


def project_fingerprint(values: Mapping[str, float]) -> dict[str, float]:
    return {api_dimension_name(name): api_dimension_value(name, value) for name, value in values.items()}
