HearForSpeech Server Agent Notes

Purpose
- This repo powers the optional advanced-analysis API used by https://hearforspeech.com.
- The production host is https://api.hearforspeech.com.
- Keep the service practical, local-first compatible, and privacy-conscious. Do not add third-party analytics, server-side client record storage, or external AI calls without an explicit architecture change.

Current API contract
- GET /health returns service status and version.
- GET /v1/capabilities returns available engines, endpoints, retention mode, and clinical notice.
- POST /v1/analysis/parselmouth accepts one uploaded audio recording and returns acoustic metrics JSON.

POST /v1/analysis/parselmouth form fields
- file: uploaded audio file. Browser WebM and WAV should remain supported; ffmpeg converts non-WAV input when available.
- prompt_text: scripted assessment prompt or line text.
- consent_confirmed: must be true.
- retention_policy: temporary.
- X-HFS-API-Key: optional header when HFS_API_KEY is configured.

Clinical and privacy rules
- Returned values are objective acoustic descriptors, not diagnosis, eligibility, or treatment decisions.
- Keep clinician-facing output conservative and editable.
- Process uploads temporarily and delete temporary files after analysis.
- Keep CORS scoped to approved HearForSpeech origins in production.
- Clinics remain responsible for consent, device controls, retention, backup handling, and HIPAA/FERPA compliance review.

Implementation guidance
- Prefer deterministic acoustic and alignment engines before generative summaries.
- Add engines behind explicit capabilities entries and feature labels.
- MFA forced alignment should be used for scripted prompts, not open-ended diagnosis.
- Allosaurus/phone-candidate output should stay beta/exploratory and clinician-controlled.
- Optional Gemma/local-LLM support should run as a separate configurable worker or service, never as a required request-path dependency for MVP analysis.
- If adding local LLM output, constrain it to structured draft summarization from recorded metrics and SLP-entered checklist data. Never represent it as clinical judgment.

Validation
- Run `python -m ruff check .`.
- Run `python -m pytest`.
- Build Docker when Docker Desktop/Linux engine is available.