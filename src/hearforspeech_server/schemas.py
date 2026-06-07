from typing import Literal

from pydantic import BaseModel, Field


class EngineInfo(BaseModel):
    name: str
    available: bool
    version: str | None = None
    note: str | None = None


class CapabilitiesResponse(BaseModel):
    service: str = "hearforspeech-server"
    version: str
    default_retention: Literal["temporary"] = "temporary"
    engines: list[EngineInfo]
    endpoints: list[str]
    clinical_notice: str


class AcousticMetrics(BaseModel):
    duration_seconds: float = Field(ge=0)
    sample_rate_hz: float | None = None
    channels: int | None = None
    rms_amplitude: float | None = None
    peak_amplitude: float | None = None
    zero_crossing_rate: float | None = None
    mean_intensity_db: float | None = None
    pitch_mean_hz: float | None = None
    pitch_min_hz: float | None = None
    pitch_max_hz: float | None = None
    voiced_fraction: float | None = None
    harmonics_to_noise_ratio_db: float | None = None
    jitter_local: float | None = None
    shimmer_local: float | None = None


class AnalysisResult(BaseModel):
    job_id: str
    status: Literal["complete", "failed"]
    prompt_text: str
    filename: str
    content_type: str | None
    engine: EngineInfo
    metrics: AcousticMetrics | None
    warnings: list[str]
    clinician_summary: str
    clinical_notice: str


class ErrorResponse(BaseModel):
    detail: str
