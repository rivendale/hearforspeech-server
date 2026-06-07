## Summary

Adds SLP-labeled calibration support behind the simple **Record → Stop → Analyze** workflow so confirmed clinician review can tune future candidate ranking.

## What changed

- Adds `POST /v1/analysis/calibration-profile` for summarizing local SLP review labels.
- Allows `POST /v1/analysis/speech-sound-patterns` to receive optional `calibration_json`.
- Applies small conservative score-ranking adjustments when at least two confirmed/ruled-out labels exist for a target/error pattern.
- Returns `calibration_profile` and `SLP calibration labels` review facts when labels are supplied.
- Surfaces MFA readiness only when the executable plus acoustic model/dictionary configuration are present.
- Documents optional MFA/Allosaurus setup and no-server-storage calibration boundaries.

## Why this helps SLPs

The frontend can now send SLP-confirmed labels back with future analysis requests so the analyzer learns which candidate patterns are useful for that patient/workflow. This improves review ordering while keeping final interpretation under clinician control.

## Data/privacy notes

- Upload handling remains consent-gated and temporary-processing only.
- Calibration labels are request payloads only; the hosted API does not store them.
- No cloud record storage, third-party analytics, or external AI calls are added.
- Candidate error patterns are not diagnoses, eligibility decisions, or replacements for SLP judgment.

## Testing performed

- `python -m ruff check .`
- `python -m pytest`

## Known limitations / follow-up ideas

- MFA alignment still needs validated acoustic model/dictionary deployment before timestamps can be added.
- Allosaurus output is optional and exploratory; production deployments need dependency/model validation.
- Future work can use exported SLP-labeled samples to validate target-specific acoustic models for /r/, sibilants, clusters, and phonological-process summaries.
