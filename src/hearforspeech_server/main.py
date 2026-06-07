import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from hearforspeech_server import __version__
from hearforspeech_server.analysis import analyze_recording
from hearforspeech_server.analysis.audio_io import extension_for_upload
from hearforspeech_server.analysis.parselmouth_metrics import parselmouth_engine_info
from hearforspeech_server.analysis.pipeline import CLINICAL_NOTICE
from hearforspeech_server.schemas import (
    AnalysisResult,
    AssessmentSessionAnalysisResult,
    AssessmentSessionInput,
    AssessmentSessionItemResult,
    CapabilitiesResponse,
    EngineInfo,
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


def require_api_key(settings: SettingsDependency, x_hfs_api_key: ApiKeyHeader = None) -> None:
    if settings.api_key and x_hfs_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-HFS-API-Key.",
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "hearforspeech-server", "version": __version__}


@app.get("/v1/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        version=__version__,
        engines=[
            parselmouth_engine_info(),
            EngineInfo(
                name="mfa",
                available=False,
                note="Planned for scripted prompt forced alignment.",
            ),
            EngineInfo(
                name="allosaurus",
                available=False,
                note="Planned beta/exploratory phone-candidate mode.",
            ),
        ],
        endpoints=[
            "GET /health",
            "GET /v1/capabilities",
            "POST /v1/analysis/parselmouth",
            "POST /v1/analysis/assessment-session",
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


@app.post("/v1/analysis/parselmouth", response_model=AnalysisResult)
async def run_parselmouth_analysis(
    file: Annotated[UploadFile, File()],
    consent_confirmed: Annotated[bool, Form()],
    _: Annotated[None, Depends(require_api_key)],
    settings: SettingsDependency,
    prompt_text: Annotated[str, Form()] = "",
    retention_policy: Annotated[str, Form()] = "temporary",
) -> AnalysisResult:
    validate_analysis_request(consent_confirmed, retention_policy)

    return await analyze_upload(file, settings=settings, prompt_text=prompt_text)


@app.post("/v1/analysis/assessment-session", response_model=AssessmentSessionAnalysisResult)
async def run_assessment_session_analysis(
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
            analysis = await analyze_upload(upload, settings=settings, prompt_text=item.prompt)
            facts = [*item_facts, metric_fact(analysis)]
            item_results.append(
                AssessmentSessionItemResult(
                    item_id=item.id,
                    prompt=item.prompt,
                    status="complete",
                    analysis=analysis,
                    warnings=analysis.warnings,
                    summary_facts=facts,
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
