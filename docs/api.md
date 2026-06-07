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

## `POST /v1/analysis/speech-sound-patterns`

Synchronous endpoint for one scripted recording. Use this for the app’s simple **Record → Stop → Analyze** workflow.

### Form fields

- `file`: audio upload. WAV/WebM/MP3/M4A/OGG are accepted when conversion support is available.
- `prompt_text`: the exact words, sentence, or `/phoneme/` targets the patient read or imitated.
- `consent_confirmed`: must be `true`.
- `retention_policy`: currently only `temporary`.

### Response

Returns:

- `job_id`
- `engines`
- `metrics`
- `possible_errors`
- `review_facts`
- `warnings`
- `clinician_summary`
- `clinical_notice`

`possible_errors` are conservative candidates for SLP review, such as possible distortion, omission, substitution, cluster reduction, or recording-quality/intelligibility flags. They are not diagnoses and should be confirmed or ignored by the clinician before documentation.

Each candidate can include:

- `target`: expected sound or sound class, such as `/r/` or `cluster`.
- `target_word`: scripted word that triggered the review item when available.
- `word_position`: initial, medial, final, vocalic, or cluster context when available.
- `category`: broad inventory category such as residual sound, sibilant, or cluster.
- `score`: ranking score from 0 to 1 for ordering review items; it is not an accuracy percentage.
- `evidence`: plain-language facts the clinician can use while replaying the sample.
