from pathlib import Path
from wave import open as wave_open

from hearforspeech_server.schemas import AcousticMetrics


def analyze_wav_basic(path: Path) -> AcousticMetrics:
    with wave_open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frame_count = wav_file.getnframes()
        frames = wav_file.readframes(frame_count)

    duration = frame_count / sample_rate if sample_rate else 0
    if sample_width != 2 or not frames:
        return AcousticMetrics(
            duration_seconds=round(duration, 4),
            sample_rate_hz=sample_rate,
            channels=channels,
        )

    sample_count = len(frames) // 2
    values = [
        int.from_bytes(frames[index : index + 2], "little", signed=True)
        for index in range(0, len(frames), 2)
    ]
    scale = 32768.0
    normalized = [value / scale for value in values]
    peak = max((abs(value) for value in normalized), default=0)
    rms = (sum(value * value for value in normalized) / sample_count) ** 0.5 if sample_count else 0
    crossings = sum(
        1
        for index in range(1, len(normalized))
        if _crosses_zero(normalized[index - 1], normalized[index])
    )

    return AcousticMetrics(
        duration_seconds=round(duration, 4),
        sample_rate_hz=sample_rate,
        channels=channels,
        rms_amplitude=round(rms, 6),
        peak_amplitude=round(peak, 6),
        zero_crossing_rate=round(crossings / duration, 4) if duration else None,
    )


def _crosses_zero(previous: float, current: float) -> bool:
    return (previous < 0 <= current) or (previous > 0 >= current)
