from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from hearforspeech_server import __version__
from hearforspeech_server.analysis import analyze_recording
from hearforspeech_server.analysis.audio_io import extension_for_upload
from hearforspeech_server.analysis.parselmouth_metrics import parselmouth_engine_info
from hearforspeech_server.analysis.pipeline import CLINICAL_NOTICE
from hearforspeech_server.schemas import AnalysisResult, CapabilitiesResponse, EngineInfo
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
        ],
        clinical_notice=CLINICAL_NOTICE,
    )


@app.post("/v1/analysis/parselmouth", response_model=AnalysisResult)
async def run_parselmouth_analysis(
    file: Annotated[UploadFile, File()],
    consent_confirmed: Annotated[bool, Form()],
    _: Annotated[None, Depends(require_api_key)],
    settings: SettingsDependency,
    prompt_text: Annotated[str, Form()] = "",
    retention_policy: Annotated[str, Form()] = "temporary",
) -> AnalysisResult:
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
