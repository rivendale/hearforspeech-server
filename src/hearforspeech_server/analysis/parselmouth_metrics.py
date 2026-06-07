from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from hearforspeech_server.schemas import AcousticMetrics, EngineInfo


def parselmouth_engine_info() -> EngineInfo:
    try:
        import parselmouth  # noqa: F401

        try:
            package_version = version("praat-parselmouth")
        except PackageNotFoundError:
            package_version = None
        return EngineInfo(name="parselmouth", available=True, version=package_version)
    except Exception as exc:  # pragma: no cover - depends on optional install
        return EngineInfo(
            name="parselmouth",
            available=False,
            note=f"Parselmouth unavailable: {exc.__class__.__name__}",
        )


def _safe_praat_call(*args: Any) -> float | None:
    try:
        import parselmouth

        value = parselmouth.praat.call(*args)
        if isinstance(value, (float, int)):
            return float(value)
    except Exception:
        return None
    return None


def _round_or_none(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None else None


def analyze_with_parselmouth(path: Path) -> AcousticMetrics:
    import parselmouth

    sound = parselmouth.Sound(str(path))
    duration = sound.get_total_duration()
    sample_rate = float(sound.sampling_frequency)
    channels = int(sound.n_channels)

    pitch = sound.to_pitch()
    pitch_mean = _safe_praat_call(pitch, "Get mean", 0, 0, "Hertz")
    pitch_min = _safe_praat_call(pitch, "Get minimum", 0, 0, "Hertz", "Parabolic")
    pitch_max = _safe_praat_call(pitch, "Get maximum", 0, 0, "Hertz", "Parabolic")

    voiced_frame_count = _safe_praat_call(pitch, "Count voiced frames")
    total_frame_count = _safe_praat_call(pitch, "Get number of frames")
    voiced_fraction = (
        voiced_frame_count / total_frame_count
        if voiced_frame_count is not None and total_frame_count
        else None
    )

    intensity = sound.to_intensity()
    mean_intensity = _safe_praat_call(intensity, "Get mean", 0, 0, "energy")

    harmonicity = sound.to_harmonicity_cc()
    hnr = _safe_praat_call(harmonicity, "Get mean", 0, 0)

    point_process = None
    try:
        point_process = parselmouth.praat.call(sound, "To PointProcess (periodic, cc)", 75, 500)
    except Exception:
        point_process = None

    jitter = (
        _safe_praat_call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
        if point_process is not None
        else None
    )
    shimmer = (
        _safe_praat_call(
            [sound, point_process],
            "Get shimmer (local)",
            0,
            0,
            0.0001,
            0.02,
            1.3,
            1.6,
        )
        if point_process is not None
        else None
    )

    return AcousticMetrics(
        duration_seconds=round(duration, 4),
        sample_rate_hz=sample_rate,
        channels=channels,
        mean_intensity_db=_round_or_none(mean_intensity),
        pitch_mean_hz=_round_or_none(pitch_mean),
        pitch_min_hz=_round_or_none(pitch_min),
        pitch_max_hz=_round_or_none(pitch_max),
        voiced_fraction=_round_or_none(voiced_fraction),
        harmonics_to_noise_ratio_db=_round_or_none(hnr),
        jitter_local=_round_or_none(jitter, 6),
        shimmer_local=_round_or_none(shimmer, 6),
    )
