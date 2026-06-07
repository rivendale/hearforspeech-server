## Summary

Adds GitHub Actions deployment automation for the Fly-hosted HearForSpeech analysis API.

## What changed

- Adds `.github/workflows/fly-deploy.yml`.
- Deploys automatically on pushes to `main`.
- Allows manual deployment through `workflow_dispatch`.
- Uses `flyctl deploy --remote-only` and `fly.toml`.
- Verifies production health at `https://api.hearforspeech.com/health`.
- Documents the required `FLY_API_TOKEN` GitHub secret.

## Why this helps SLPs

Backend analysis improvements become available through the app immediately after merge, instead of relying on a manual deploy step.

## Data/privacy notes

- No API behavior, data retention, or analysis processing changes are included.
- The service remains temporary-processing only by default.
- No cloud record storage, analytics, or external AI calls are added.

## Testing performed

- `python -m ruff check .`
- `python -m pytest`

## Known limitations / follow-up ideas

- The GitHub repo needs a `FLY_API_TOKEN` secret before the workflow can deploy.
- Future work could add deployment status badges and post-deploy capability smoke tests.
