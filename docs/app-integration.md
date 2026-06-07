# HearForSpeech App Integration

The PWA should add an optional panel named **Run Advanced Analysis**.

## UI Requirements

- Hidden by default behind an explicit action.
- Explain that audio leaves the device for processing.
- Require consent before upload.
- Show retention policy: temporary processing only for MVP.
- Show the configured API URL.
- Keep generated results editable.
- Phrase outputs as supporting metrics and “Consider...” observations.

## Suggested Flow

1. SLP records a line in an assessment or session.
2. SLP taps **Run Advanced Analysis**.
3. Modal displays:
   - file/recording name
   - prompt text
   - backend URL
   - consent checkbox
   - retention warning
4. App uploads the audio and prompt text.
5. App displays:
   - duration
   - pitch/intensity metrics when available
   - warnings
   - clinician summary
6. SLP taps **Insert into note** or **Discard**.

## Environment

The PWA can use:

```text
VITE_HFS_ANALYSIS_API_URL=https://api.hearforspeech.com
```

If unset, hide the backend upload button or show a local-only explanation.
