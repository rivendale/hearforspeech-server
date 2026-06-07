from pathlib import Path
from uuid import uuid4

from hearforspeech_server.analysis.audio_io import convert_to_wav_if_needed
from hearforspeech_server.analysis.parselmouth_metrics import (
    analyze_with_parselmouth,
    parselmouth_engine_info,
)
from hearforspeech_server.analysis.wav_metrics import analyze_wav_basic
from hearforspeech_server.schemas import AcousticMetrics, AnalysisFact, AnalysisResult, EngineInfo

CLINICAL_NOTICE = (
    "These metrics are objective acoustic descriptors only. They do not diagnose, "
    "determine eligibility, or replace SLP interpretation."
)


def summarize_metrics(prompt_text: str, engine: EngineInfo, warnings: list[str]) -> str:
    prompt_part = f' for prompt "{prompt_text.strip()}"' if prompt_text.strip() else ""
    warning_part = f" Warnings: {'; '.join(warnings)}" if warnings else ""
    return (
        f"Advanced analysis completed{prompt_part} using {engine.name}. "
        "Review the recording and metrics alongside the guided assessment checklist before "
        "documenting clinical interpretation."
        f"{warning_part}"
    )


def build_review_facts(metrics: AcousticMetrics | None, engine: EngineInfo) -> list[AnalysisFact]:
    if metrics is None:
        return []

    caution = "Objective descriptor for SLP review only."
    facts = [
        AnalysisFact(
            label="Recording duration",
            value=f"{metrics.duration_seconds:.2f}",
            unit="seconds",
            source=engine.name,
            caution=caution,
        )
    ]
    if metrics.pitch_mean_hz is not None:
        facts.append(
            AnalysisFact(
                label="Mean pitch",
                value=f"{metrics.pitch_mean_hz:.1f}",
                unit="Hz",
                source=engine.name,
                caution=caution,
            )
        )
    if metrics.mean_intensity_db is not None:
        facts.append(
            AnalysisFact(
                label="Mean intensity",
                value=f"{metrics.mean_intensity_db:.1f}",
                unit="dB",
                source=engine.name,
                caution=caution,
            )
        )
    if metrics.voiced_fraction is not None:
        facts.append(
            AnalysisFact(
                label="Voiced fraction",
                value=f"{metrics.voiced_fraction:.2f}",
                source=engine.name,
                caution=caution,
            )
        )
    if metrics.zero_crossing_rate is not None:
        facts.append(
            AnalysisFact(
                label="Zero-crossing rate",
                value=f"{metrics.zero_crossing_rate:.1f}",
                unit="per second",
                source=engine.name,
                caution=caution,
            )
        )
    return facts


def analyze_recording(
    path: Path,
    *,
    prompt_text: str,
    filename: str,
    content_type: str | None,
) -> AnalysisResult:
    job_id = str(uuid4())
    temp_paths: list[Path] = []
    conversion_warnings: list[str] = []
    analysis_path = path

    try:
        analysis_path, temp_paths, conversion_warnings = convert_to_wav_if_needed(path)
        parselmouth_engine = parselmouth_engine_info()

        if parselmouth_engine.available:
            try:
                metrics = analyze_with_parselmouth(analysis_path)
                engine = parselmouth_engine
                warnings = conversion_warnings
            except Exception as exc:
                metrics = analyze_wav_basic(analysis_path)
                engine = EngineInfo(
                    name="basic-wav",
                    available=True,
                    note="Parselmouth failed; returned basic WAV metrics.",
                )
                warnings = [
                    *conversion_warnings,
                    f"Parselmouth analysis failed: {exc.__class__.__name__}. "
                    "Basic WAV metrics returned.",
                ]
        else:
            metrics = analyze_wav_basic(analysis_path)
            engine = EngineInfo(
                name="basic-wav",
                available=True,
                note="Install praat-parselmouth for acoustic voice metrics.",
            )
            warnings = [
                *conversion_warnings,
                "Parselmouth is not installed; returned basic WAV metrics only.",
            ]

        return AnalysisResult(
            job_id=job_id,
            status="complete",
            prompt_text=prompt_text,
            filename=filename,
            content_type=content_type,
            engine=engine,
            metrics=metrics,
            review_facts=build_review_facts(metrics, engine),
            warnings=warnings,
            clinician_summary=summarize_metrics(prompt_text, engine, warnings),
            clinical_notice=CLINICAL_NOTICE,
        )
    finally:
        for temp_path in temp_paths:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
