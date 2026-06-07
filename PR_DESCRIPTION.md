## Summary

Improves the speech-sound analyzer behind the simple **Record → Stop → Analyze** workflow so review items are more target-specific and easier for an SLP to confirm.

## What changed

- Adds word-level target parsing for common adolescent inventory prompts, word positions, clusters, residual sounds, and sibilants.
- Returns richer `possible_errors` with `target_word`, `word_position`, `category`, `score`, and evidence fields.
- Ranks possible distortion, omission, substitution, cluster reduction, and recording-quality/intelligibility candidates for faster SLP review.
- Merges basic waveform metrics with Parselmouth metrics so recordings keep useful amplitude/zero-crossing facts even when Praat metrics are available.
- Uses Allosaurus phone candidates when installed while keeping output beta/exploratory and SLP-reviewed.
- Updates API docs, README, and tests for the enriched candidate schema.

## Why this helps SLPs

The frontend can now present more useful “possible speech-sound errors” immediately after recording: which scripted word/position needs review, why it was flagged, and how strongly it should be prioritized. The clinician can replay the sample and confirm or ignore each candidate.

## Data/privacy notes

- Upload handling remains consent-gated and temporary-processing only.
- No cloud record storage, third-party analytics, or external AI calls are added.
- Candidate error patterns are not diagnoses, eligibility decisions, or replacements for SLP judgment.

## Testing performed

- `python -m ruff check .`
- `python -m pytest`

## Known limitations / follow-up ideas

- MFA alignment requires acoustic models/dictionaries before true timestamps can be added.
- Allosaurus output is optional and exploratory; production deployments need dependency/model validation.
- Future work can add MFA timestamps, calibrated target-specific acoustic models for /r/, sibilants, clusters, and phonological-process summaries.
