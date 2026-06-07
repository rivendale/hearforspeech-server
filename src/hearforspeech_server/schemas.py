from typing import Literal

from pydantic import BaseModel, Field


class EngineInfo(BaseModel):
    name: str
    available: bool
    version: str | None = None
    note: str | None = None


class CapabilityLimits(BaseModel):
    max_upload_mb: int
    max_batch_files: int
    default_retention: Literal["temporary"] = "temporary"
    accepted_audio_types: list[str] = Field(default_factory=list)


class CapabilitiesResponse(BaseModel):
    service: str = "hearforspeech-server"
    version: str
    default_retention: Literal["temporary"] = "temporary"
    engines: list[EngineInfo]
    endpoints: list[str]
    limits: CapabilityLimits | None = None
    workflow_notes: list[str] = Field(default_factory=list)
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


class AnalysisFact(BaseModel):
    label: str
    value: str
    unit: str | None = None
    source: str
    caution: str | None = None


class SpeechSoundCandidate(BaseModel):
    target: str
    target_word: str | None = None
    word_position: str | None = None
    category: str | None = None
    expected: str | None = None
    observed: str | None = None
    error_type: Literal[
        "possible_substitution",
        "possible_omission",
        "possible_distortion",
        "possible_cluster_reduction",
        "possible_rate_or_intelligibility",
        "needs_review",
    ]
    confidence: Literal["low", "medium", "high"]
    score: float = Field(ge=0, le=1, default=0.25)
    evidence: list[str] = Field(default_factory=list)
    start_seconds: float | None = None
    end_seconds: float | None = None
    review_prompt: str


class AnalysisResult(BaseModel):
    job_id: str
    request_id: str | None = None
    status: Literal["complete", "failed"]
    prompt_text: str
    filename: str
    content_type: str | None
    engine: EngineInfo
    metrics: AcousticMetrics | None
    review_facts: list[AnalysisFact] = Field(default_factory=list)
    warnings: list[str]
    clinician_summary: str
    clinical_notice: str


class SpeechSoundAnalysisResult(BaseModel):
    job_id: str
    request_id: str | None = None
    status: Literal["complete", "failed"]
    prompt_text: str
    filename: str
    content_type: str | None
    engines: list[EngineInfo]
    metrics: AcousticMetrics | None
    possible_errors: list[SpeechSoundCandidate] = Field(default_factory=list)
    review_facts: list[AnalysisFact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    clinician_summary: str
    clinical_notice: str


class AssessmentSessionItemInput(BaseModel):
    id: str
    prompt: str
    section_title: str | None = None
    kind: str | None = None
    result: str | None = None
    notes: str | None = None
    cue_level: str | None = None
    recording_filename: str | None = None


class AssessmentSessionInput(BaseModel):
    assessment_id: str | None = None
    client_label: str | None = None
    items: list[AssessmentSessionItemInput]


class AssessmentSessionItemResult(BaseModel):
    item_id: str
    prompt: str
    status: Literal["complete", "no_recording", "failed"]
    analysis: AnalysisResult | None = None
    warnings: list[str]
    summary_facts: list[str]
    review_facts: list[AnalysisFact] = Field(default_factory=list)


class AssessmentSessionAnalysisResult(BaseModel):
    job_id: str
    request_id: str | None = None
    status: Literal["complete", "partial", "failed"]
    assessment_id: str | None = None
    client_label: str | None = None
    total_items: int
    analyzed_items: int
    item_results: list[AssessmentSessionItemResult]
    summary_ready_facts: list[str]
    warnings: list[str]
    clinical_notice: str


class ErrorResponse(BaseModel):
    detail: str
