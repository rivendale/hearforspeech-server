## Summary

Adds a speech-sound pattern analysis endpoint for the simple **Record → Stop → Analyze** workflow.

## What changed

- Adds `POST /v1/analysis/speech-sound-patterns`.
- Returns conservative `possible_errors` such as possible distortion, omission, substitution, cluster reduction, or recording-quality/intelligibility flags.
- Parses expected targets from scripted prompts and common adolescent speech-inventory words.
- Includes Parselmouth/basic acoustic metrics as review facts.
- Reports MFA and Allosaurus capability status.
- Uses Allosaurus phone candidates when Allosaurus is installed, while keeping output beta/exploratory and SLP-reviewed.
- Updates capabilities, API docs, README, and tests.

## Why this helps SLPs

The frontend can now present “possible speech-sound errors” immediately after recording, instead of only showing acoustic metrics. The clinician can replay the sample and confirm or ignore each candidate.

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
- Future work can add target-specific acoustic models for /r/, sibilants, clusters, and phonological-process summaries.
