# API Contract

Base URL for production is intended to be:

```text
https://api.hearforspeech.com
```

## `GET /health`

Returns service status.

## `GET /v1/capabilities`

Returns available analysis engines and planned engines.

The PWA should call this before showing advanced-analysis actions.

## `POST /v1/analysis/parselmouth`

Synchronous MVP endpoint for one recording.

### Form fields

- `file`: audio upload. WAV is preferred. Docker image includes `ffmpeg` to convert WebM/MP3/M4A to WAV.
- `prompt_text`: the exact script or prompt the patient read/spoke.
- `consent_confirmed`: must be `true`.
- `retention_policy`: currently only `temporary`.

### Headers

- `X-HFS-API-Key`: required only if the deployment sets `HFS_API_KEY`.

### Response

Returns:

- `job_id`
- `engine`
- `metrics`
- `warnings`
- `clinician_summary`
- `clinical_notice`

The app should import this as editable supporting data, not as a diagnosis.
