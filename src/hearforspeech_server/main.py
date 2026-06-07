import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from hearforspeech_server import __version__
from hearforspeech_server.analysis import analyze_recording
from hearforspeech_server.analysis.audio_io import extension_for_upload
from hearforspeech_server.analysis.parselmouth_metrics import parselmouth_engine_info
from hearforspeech_server.analysis.pipeline import CLINICAL_NOTICE
from hearforspeech_server.analysis.speech_sound_patterns import (
    allosaurus_engine_info,
    analyze_speech_sound_patterns,
    mfa_engine_info,
)
from hearforspeech_server.schemas import (
    AnalysisResult,
    AssessmentSessionAnalysisResult,
    AssessmentSessionInput,
    AssessmentSessionItemResult,
    CapabilitiesResponse,
    CapabilityLimits,
    EngineInfo,
    SpeechSoundAnalysisResult,
)
from hearforspeech_server.settings import Settings, get_settings

app = FastAPI(
    title="HearForSpeech Server",
    version=__version__,
    description="Optional advanced analysis backend for HearForSpeech.",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-HFS-API-Key"],
)


SettingsDependency = Annotated[Settings, Depends(get_settings)]
ApiKeyHeader = Annotated[str | None, Header()]
MAX_FACTS_PER_ITEM = 8


@app.middleware("http")
async def add_request_id(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request_id = request.headers.get("X-HFS-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    start_time = perf_counter()
    response = await call_next(request)
    response.headers["X-HFS-Request-ID"] = request_id
    response.headers["X-HFS-Processing-Ms"] = str(round((perf_counter() - start_time) * 1000, 2))
    return response


def require_api_key(settings: SettingsDependency, x_hfs_api_key: ApiKeyHeader = None) -> None:
    if settings.api_key and x_hfs_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-HFS-API-Key.",
        )


@app.get("/health")
def health(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "service": "hearforspeech-server",
        "version": __version__,
        "request_id": request.state.request_id,
    }


@app.get("/v1/capabilities", response_model=CapabilitiesResponse)
def capabilities(settings: SettingsDependency) -> CapabilitiesResponse:
    return CapabilitiesResponse(
        version=__version__,
        engines=[
            parselmouth_engine_info(),
            mfa_engine_info(),
            allosaurus_engine_info(),
            EngineInfo(
                name="speech-sound-patterns",
                available=True,
                note=(
                    "Conservative candidate error-pattern review from prompt targets, "
                    "acoustics, and optional phone candidates."
                ),
            ),
        ],
        endpoints=[
            "GET /health",
            "GET /v1/capabilities",
            "POST /v1/analysis/parselmouth",
            "POST /v1/analysis/speech-sound-patterns",
            "POST /v1/analysis/assessment-session",
        ],
        limits=CapabilityLimits(
            max_upload_mb=settings.max_upload_mb,
            max_batch_files=settings.max_batch_files,
            accepted_audio_types=[
                "audio/wav",
                "audio/webm",
                "audio/mp4",
                "audio/mpeg",
                "audio/ogg",
            ],
        ),
        workflow_notes=[
            "Use scripted-prompt uploads for best future forced-alignment support.",
            "Speech-sound pattern candidates require SLP confirmation before documentation.",
            "Use returned review_facts as supporting facts for clinician review, not conclusions.",
            "Temporary processing only; do not send audio without consent.",
        ],
        clinical_notice=CLINICAL_NOTICE,
    )


def validate_analysis_request(consent_confirmed: bool, retention_policy: str) -> None:
    if not consent_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent must be confirmed before uploading audio for analysis.",
        )
    if retention_policy != "temporary":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MVP only supports temporary processing retention.",
        )


def upload_lookup_key(filename: str | None) -> str:
    if not filename:
        return ""
    return Path(filename).stem.strip().lower()


def metric_fact(result: AnalysisResult) -> str:
    metrics = result.metrics
    if not metrics:
        return f"{result.prompt_text or result.filename}: acoustic metrics were not available."

    label = result.prompt_text or result.filename
    parts = [f"{label}: duration {metrics.duration_seconds:.2f} sec"]
    if metrics.pitch_mean_hz is not None:
        parts.append(f"mean pitch {metrics.pitch_mean_hz:.1f} Hz")
    if metrics.mean_intensity_db is not None:
        parts.append(f"mean intensity {metrics.mean_intensity_db:.1f} dB")
    if metrics.voiced_fraction is not None:
        parts.append(f"voiced fraction {metrics.voiced_fraction:.2f}")
    return "; ".join(parts)


def attach_request_id(result: AnalysisResult, request_id: str) -> AnalysisResult:
    return result.model_copy(update={"request_id": request_id})


async def analyze_upload(
    file: UploadFile,
    *,
    settings: Settings,
    prompt_text: str,
) -> AnalysisResult:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    suffix = extension_for_upload(file.filename, file.content_type)
    total_bytes = 0
    temp_path: Path | None = None

    try:
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Upload exceeds {settings.max_upload_mb} MB limit.",
                    )
                temp_file.write(chunk)

        return analyze_recording(
            temp_path,
            prompt_text=prompt_text,
            filename=file.filename or "recording",
            content_type=file.content_type,
        )
    finally:
        await file.close()
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


async def analyze_upload_speech_sound_patterns(
    file: UploadFile,
    *,
    settings: Settings,
    prompt_text: str,
) -> SpeechSoundAnalysisResult:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    suffix = extension_for_upload(file.filename, file.content_type)
    total_bytes = 0
    temp_path: Path | None = None

    try:
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Upload exceeds {settings.max_upload_mb} MB limit.",
                    )
                temp_file.write(chunk)

        return analyze_speech_sound_patterns(
            temp_path,
            prompt_text=prompt_text,
            filename=file.filename or "recording",
            content_type=file.content_type,
        )
    finally:
        await file.close()
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


@app.post("/v1/analysis/parselmouth", response_model=AnalysisResult)
async def run_parselmouth_analysis(
    request: Request,
    file: Annotated[UploadFile, File()],
    consent_confirmed: Annotated[bool, Form()],
    _: Annotated[None, Depends(require_api_key)],
    settings: SettingsDependency,
    prompt_text: Annotated[str, Form()] = "",
    retention_policy: Annotated[str, Form()] = "temporary",
) -> AnalysisResult:
    validate_analysis_request(consent_confirmed, retention_policy)

    result = await analyze_upload(file, settings=settings, prompt_text=prompt_text)
    return attach_request_id(result, request.state.request_id)


@app.post("/v1/analysis/speech-sound-patterns", response_model=SpeechSoundAnalysisResult)
async def run_speech_sound_pattern_analysis(
    request: Request,
    file: Annotated[UploadFile, File()],
    consent_confirmed: Annotated[bool, Form()],
    _: Annotated[None, Depends(require_api_key)],
    settings: SettingsDependency,
    prompt_text: Annotated[str, Form()] = "",
    retention_policy: Annotated[str, Form()] = "temporary",
) -> SpeechSoundAnalysisResult:
    validate_analysis_request(consent_confirmed, retention_policy)

    result = await analyze_upload_speech_sound_patterns(
        file,
        settings=settings,
        prompt_text=prompt_text,
    )
    return result.model_copy(update={"request_id": request.state.request_id})


@app.post("/v1/analysis/assessment-session", response_model=AssessmentSessionAnalysisResult)
async def run_assessment_session_analysis(
    request: Request,
    consent_confirmed: Annotated[bool, Form()],
    _: Annotated[None, Depends(require_api_key)],
    settings: SettingsDependency,
    assessment_json: Annotated[str, Form()],
    files: Annotated[list[UploadFile] | None, File()] = None,
    retention_policy: Annotated[str, Form()] = "temporary",
) -> AssessmentSessionAnalysisResult:
    validate_analysis_request(consent_confirmed, retention_policy)

    try:
        assessment = AssessmentSessionInput.model_validate(json.loads(assessment_json))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assessment_json must be valid assessment-session JSON.",
        ) from exc

    uploads = files or []
    if len(uploads) > settings.max_batch_files:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch upload exceeds {settings.max_batch_files} file limit.",
        )

    uploads_by_key = {
        upload_lookup_key(file.filename): file
        for file in uploads
        if upload_lookup_key(file.filename)
    }
    used_keys: set[str] = set()
    item_results: list[AssessmentSessionItemResult] = []
    warnings: list[str] = []
    summary_ready_facts: list[str] = []

    for item in assessment.items:
        requested_keys = [
            item.id.strip().lower(),
            upload_lookup_key(item.recording_filename),
        ]
        upload_key = next((key for key in requested_keys if key and key in uploads_by_key), "")
        upload = uploads_by_key.get(upload_key)
        item_facts = [
            f"{item.section_title or 'Assessment line'}: {item.result or 'not scored'}."
        ]
        if item.notes:
            item_facts.append(f"SLP note: {item.notes}")
        if item.cue_level:
            item_facts.append(f"Cue level: {item.cue_level}")

        if upload is None:
            item_results.append(
                AssessmentSessionItemResult(
                    item_id=item.id,
                    prompt=item.prompt,
                    status="no_recording",
                    analysis=None,
                    warnings=["No matching uploaded recording for this assessment line."],
                    summary_facts=item_facts,
                )
            )
            summary_ready_facts.extend(item_facts)
            continue

        used_keys.add(upload_key)
        try:
            analysis = attach_request_id(
                await analyze_upload(upload, settings=settings, prompt_text=item.prompt),
                request.state.request_id,
            )
            facts = [*item_facts, metric_fact(analysis)]
            item_results.append(
                AssessmentSessionItemResult(
                    item_id=item.id,
                    prompt=item.prompt,
                    status="complete",
                    analysis=analysis,
                    warnings=analysis.warnings,
                    summary_facts=facts,
                    review_facts=analysis.review_facts[:MAX_FACTS_PER_ITEM],
                )
            )
            summary_ready_facts.extend(facts)
            warnings.extend(analysis.warnings)
        except HTTPException:
            raise
        except Exception as exc:
            item_warning = f"Analysis failed for {item.id}: {exc.__class__.__name__}."
            warnings.append(item_warning)
            item_results.append(
                AssessmentSessionItemResult(
                    item_id=item.id,
                    prompt=item.prompt,
                    status="failed",
                    analysis=None,
                    warnings=[item_warning],
                    summary_facts=item_facts,
                )
            )
            summary_ready_facts.extend(item_facts)

    for upload in uploads:
        key = upload_lookup_key(upload.filename)
        if key not in used_keys:
            await upload.close()

    analyzed_items = sum(1 for item in item_results if item.status == "complete")
    if analyzed_items == 0 and uploads:
        session_status = "failed"
    elif analyzed_items < len(uploads) or any(item.status == "failed" for item in item_results):
        session_status = "partial"
    else:
        session_status = "complete"

    return AssessmentSessionAnalysisResult(
        job_id=str(uuid4()),
        request_id=request.state.request_id,
        status=session_status,
        assessment_id=assessment.assessment_id,
        client_label=assessment.client_label,
        total_items=len(assessment.items),
        analyzed_items=analyzed_items,
        item_results=item_results,
        summary_ready_facts=[
            (
                "Assessment session analysis completed for "
                f"{analyzed_items} recording(s) across {len(assessment.items)} checklist line(s)."
            ),
            *summary_ready_facts,
            CLINICAL_NOTICE,
        ],
        warnings=warnings,
        clinical_notice=CLINICAL_NOTICE,
    )
