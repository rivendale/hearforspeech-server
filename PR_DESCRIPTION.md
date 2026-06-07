## Summary

Hardens the analysis API contract with request IDs, capability limits, batch-size limits, and deterministic review facts for the frontend Diagnostic Portal.

## What changed

- Adds `X-HFS-Request-ID` and `X-HFS-Processing-Ms` response headers.
- Allows callers to send `X-HFS-Request-ID` for frontend/backend correlation.
- Adds capability `limits` and clinician workflow notes to `/v1/capabilities`.
- Adds configurable `HFS_MAX_BATCH_FILES`.
- Enforces batch file-count limits on `POST /v1/analysis/assessment-session`.
- Adds deterministic `review_facts` to single and batch analysis responses.
- Adds tests for request IDs, limits, and review facts.

## Why this helps SLPs

The frontend can show safer, clearer analysis state: objective facts for clinician review, visible upload limits, and request IDs for support/debugging without storing clinical records on the server.

## Data/privacy notes

- Raw audio remains temporary processing input.
- Review facts are objective acoustic descriptors only.
- No third-party analytics, server-side client record storage, or external AI calls are added.

## Testing performed

- `python -m ruff check .`
- `python -m pytest`

## Known limitations / follow-up ideas

- MFA forced alignment remains the next major analysis engine.
- Review facts are deterministic metrics, not automated interpretation.
- Long-running job persistence is still future work.
