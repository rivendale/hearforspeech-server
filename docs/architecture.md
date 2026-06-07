# Architecture

HearForSpeech uses a split architecture:

- `rivendale/hearforspeech`: static local-first PWA hosted on GitHub Pages.
- `rivendale/hearforspeech-server`: optional backend for advanced analysis.

## Why Separate Repos

Separate repos keep the PWA simple and deployable to GitHub Pages while isolating heavy Python dependencies such as Parselmouth, MFA, Kaldi, and Allosaurus. The backend can have its own Docker image, runtime, security controls, and release cadence.

## Privacy-First Flow

1. The SLP records and documents locally in the PWA.
2. The SLP explicitly chooses **Run Advanced Analysis**.
3. The PWA shows consent and retention warnings.
4. The recording and prompt text upload to the backend.
5. The backend processes the file temporarily.
6. The backend returns structured JSON.
7. The PWA imports results into editable local notes.
8. The SLP decides what, if anything, belongs in documentation.

## Planned Engines

### Parselmouth/Praat

First production target. Returns acoustic descriptors such as duration, intensity, pitch, voiced fraction, harmonics-to-noise ratio, jitter, and shimmer when available.

### MFA

Planned for scripted assessment prompts where the expected transcript is known. Returns timing/alignment support, not correctness judgments by itself.

### Allosaurus

Planned beta/exploratory mode for phone-candidate output. Results should be labeled as possible phone candidates and require SLP review.

## Deployment Shape

```text
hearforspeech.com          -> GitHub Pages PWA
api.hearforspeech.com      -> FastAPI container
```

Recommended first hosts:

- Fly.io
- Render
- Railway
- Google Cloud Run
- A clinic-owned Docker host

Cloudflare can front the domain and provide DNS/TLS. Cloudflare Containers may become viable, but a conventional container host is simpler for the first clinical-analysis backend.
