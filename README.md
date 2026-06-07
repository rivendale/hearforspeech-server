# HearForSpeech Server

Optional FastAPI backend for HearForSpeech advanced speech analysis.

The main HearForSpeech app stays local-first and offline-capable at `https://hearforspeech.com`. This server is an explicit opt-in analysis service for clinicians who choose to upload a recording for additional objective metrics.

## MVP

- Upload one speech recording and prompt text.
- Run local Python analysis using Parselmouth/Praat when installed.
- Flag ranked, conservative possible speech-sound error patterns from scripted prompts, word position, acoustics, and optional phone-candidate output.
- Accept SLP-confirmed local review labels to tune candidate ranking without storing labels on the server.
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
- Speech-sound pattern responses include `possible_errors`, which are candidate patterns such as possible distortion, omission, substitution, cluster reduction, or recording-quality/intelligibility flags. Candidates can include the scripted word, word position, inventory category, review score, and evidence for SLP confirmation.
- Configure limits with:

```bash
HFS_MAX_UPLOAD_MB=50
HFS_MAX_BATCH_FILES=40
HFS_MFA_ACOUSTIC_MODEL=
HFS_MFA_DICTIONARY=
```

## Docker

```bash
docker build -t hearforspeech-server .
docker run --rm -p 8000:8000 hearforspeech-server
```

## Speech-Sound Error Pattern Analysis

`POST /v1/analysis/speech-sound-patterns` accepts one recording plus the prompt text the patient read or imitated. The endpoint returns:

- Parselmouth/basic acoustic metrics
- Expected targets parsed from scripted words, `/phoneme/` markers, word position, and common adolescent inventory prompts
- Optional Allosaurus phone candidates when Allosaurus is installed
- MFA availability status for future forced-alignment configuration
- Optional SLP calibration labels supplied as `calibration_json`
- Ranked conservative `possible_errors` for SLP review with word/context/evidence fields when available

The best results come from scripted prompts such as:

```text
Say red, rabbit, ring, car, star, sun, zoo, shoe, chair, jump, thin, this, street, tree.
```

Returned candidates are not diagnoses. A higher score only moves a candidate up the review list; it is not an accuracy percentage or diagnostic conclusion. The SLP should replay the recording and confirm/ignore each candidate before documentation.

### SLP Calibration Labels

`POST /v1/analysis/calibration-profile` accepts JSON review labels that the PWA stores locally after the SLP taps **Confirm**, **Rule out**, or **Unsure** on analyzer candidates. The server returns a calibration profile with per-target/error review counts and conservative score adjustments. The hosted API does not store those labels.

`POST /v1/analysis/speech-sound-patterns` can also receive `calibration_json` as a multipart form field. When at least two confirmed/ruled-out labels exist for a target/error pattern, the analyzer adjusts candidate ranking slightly and adds an `SLP calibration labels` review fact. Calibration only tunes review order; it is not a validated diagnostic model.

### Optional MFA and Allosaurus Setup

The Docker image keeps MFA and Allosaurus optional to avoid turning the API into a heavy model server by default.

- Allosaurus: install and validate the package/model in the deployment image before using beta phone-candidate output. Capability status reports `allosaurus` availability.
- MFA: install Montreal Forced Aligner separately, then set `HFS_MFA_ACOUSTIC_MODEL` and `HFS_MFA_DICTIONARY`. Capability status reports MFA as available only when the executable and model/dictionary configuration are present.
- The current production-safe path is still scripted prompts + Parselmouth/basic acoustics + SLP labels. MFA timestamps and Allosaurus phone candidates should remain clinician-reviewed and clearly labeled as supporting data.

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
5. SLP-labeled calibration exports for model validation and clinic-controlled quality review.
6. Self-hosting templates for clinics.
