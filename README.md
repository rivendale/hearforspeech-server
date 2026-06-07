# HearForSpeech Server

Optional FastAPI backend for HearForSpeech advanced speech analysis.

The main HearForSpeech app stays local-first and offline-capable at `https://hearforspeech.com`. This server is an explicit opt-in analysis service for clinicians who choose to upload a recording for additional objective metrics.

## MVP

- Upload one speech recording and prompt text.
- Run local Python analysis using Parselmouth/Praat when installed.
- Flag conservative possible speech-sound error patterns from scripted prompts, acoustics, and optional phone-candidate output.
- Return structured JSON that the HearForSpeech PWA can import into an editable assessment/session note.
- Keep raw audio temporary by default.

## Non-goals

- No automated diagnosis.
- No replacement for SLP judgment.
- No unreviewed phoneme/error claims. Speech-sound candidates require SLP confirmation.
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
- Speech-sound pattern responses include `possible_errors`, which are candidate patterns such as possible distortion, omission, substitution, cluster reduction, or recording-quality/intelligibility flags.
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

## Speech-Sound Error Pattern Analysis

`POST /v1/analysis/speech-sound-patterns` accepts one recording plus the prompt text the patient read or imitated. The endpoint returns:

- Parselmouth/basic acoustic metrics
- Expected targets parsed from scripted words or `/phoneme/` markers
- Optional Allosaurus phone candidates when Allosaurus is installed
- MFA availability status for future forced-alignment configuration
- Conservative `possible_errors` for SLP review

The best results come from scripted prompts such as:

```text
Say red, rabbit, ring, car, star, sun, zoo, shoe, chair, jump, thin, this, street, tree.
```

Returned candidates are not diagnoses. The SLP should replay the recording and confirm/ignore each candidate before documentation.

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
2. Conservative speech-sound pattern candidates for scripted prompts.
3. MFA alignment when deployment includes acoustic models/dictionaries.
4. Allosaurus phone-candidate mode behind a beta/exploratory label when installed.
5. Self-hosting templates for clinics.
