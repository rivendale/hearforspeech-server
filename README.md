# HearForSpeech Server

Optional FastAPI backend for HearForSpeech advanced speech analysis.

The main HearForSpeech app stays local-first and offline-capable at `https://hearforspeech.com`. This server is an explicit opt-in analysis service for clinicians who choose to upload a recording for additional objective metrics.

## MVP

- Upload one speech recording and prompt text.
- Run local Python analysis using Parselmouth/Praat when installed.
- Return structured JSON that the HearForSpeech PWA can import into an editable assessment/session note.
- Keep raw audio temporary by default.

## Non-goals

- No automated diagnosis.
- No replacement for SLP judgment.
- No required cloud dependency for the PWA.
- No long-term clinical record storage unless a deployment explicitly enables it later.

## Local Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev,analysis]"
uvicorn hearforspeech_server.main:app --reload
```

Open:

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/v1/capabilities`

## API Hardening

- Every response includes `X-HFS-Request-ID`; callers can also send that header to correlate frontend and server logs.
- `/v1/capabilities` returns upload limits, accepted audio types, and clinician-workflow notes.
- Analysis responses include `review_facts`, which are deterministic metric facts for SLP review only.
- Configure limits with:

```bash
HFS_MAX_UPLOAD_MB=50
HFS_MAX_BATCH_FILES=40
```

## Docker

```bash
docker build -t hearforspeech-server .
docker run --rm -p 8000:8000 hearforspeech-server
```

## Fly Deployment CI

The repository includes `.github/workflows/fly-deploy.yml`. It deploys automatically whenever `main` is updated and can also be run manually from GitHub Actions.

Required GitHub repository secret:

```bash
FLY_API_TOKEN=fly_api_token_with_deploy_access
```

The workflow deploys with `flyctl deploy --remote-only` using `fly.toml`, then verifies `https://api.hearforspeech.com/health`.

## Privacy Model

The PWA should show consent before upload. This server treats uploaded audio as temporary processing input and returns metrics only. Deployers are responsible for TLS, access controls, retention, logging policy, BAAs/DPAs if applicable, and HIPAA/FERPA review.

## Roadmap

1. Parselmouth acoustic metrics MVP.
2. MFA alignment for scripted prompts.
3. Allosaurus phone-candidate mode behind a beta/exploratory label.
4. Self-hosting templates for clinics.
