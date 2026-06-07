import json
from io import BytesIO
from math import sin, tau
from wave import open as wave_open

from fastapi.testclient import TestClient

from hearforspeech_server.main import app

client = TestClient(app)


def make_wav_bytes(duration_seconds: float = 0.15, sample_rate: int = 16000) -> bytes:
    buffer = BytesIO()
    with wave_open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for index in range(int(duration_seconds * sample_rate)):
            value = int(0.25 * 32767 * sin(tau * 220 * index / sample_rate))
            wav_file.writeframes(value.to_bytes(2, "little", signed=True))
    return buffer.getvalue()


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-hfs-request-id"]


def test_capabilities() -> None:
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "hearforspeech-server"
    assert "POST /v1/analysis/parselmouth" in payload["endpoints"]
    assert "POST /v1/analysis/assessment-session" in payload["endpoints"]
    assert payload["limits"]["max_upload_mb"] > 0
    assert payload["limits"]["max_batch_files"] > 0
    assert payload["workflow_notes"]


def test_analysis_requires_consent() -> None:
    response = client.post(
        "/v1/analysis/parselmouth",
        data={"prompt_text": "Say red", "consent_confirmed": "false"},
        files={"file": ("sample.wav", make_wav_bytes(), "audio/wav")},
    )
    assert response.status_code == 400


def test_analysis_returns_metrics() -> None:
    response = client.post(
        "/v1/analysis/parselmouth",
        data={"prompt_text": "Say red", "consent_confirmed": "true"},
        files={"file": ("sample.wav", make_wav_bytes(), "audio/wav")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "complete"
    assert payload["prompt_text"] == "Say red"
    assert payload["metrics"]["duration_seconds"] > 0
    assert payload["request_id"] == response.headers["x-hfs-request-id"]
    assert payload["review_facts"]
    assert "diagnose" in payload["clinical_notice"]


def test_assessment_session_analysis_returns_line_results() -> None:
    assessment_json = {
        "assessment_id": "assessment-1",
        "client_label": "Test student",
        "items": [
            {
                "id": "line-1",
                "prompt": "Say red rabbit",
                "section_title": "/r/ probe",
                "kind": "sound_probe",
                "result": "distorted",
                "notes": "Improved with slowed rate.",
                "cue_level": "minimal",
            },
            {
                "id": "line-2",
                "prompt": "Conversation sample",
                "section_title": "Connected speech",
                "kind": "speech_sample",
                "result": "monitor",
            },
        ],
    }
    response = client.post(
        "/v1/analysis/assessment-session",
        data={
            "assessment_json": json.dumps(assessment_json),
            "consent_confirmed": "true",
            "retention_policy": "temporary",
        },
        files=[("files", ("line-1.wav", make_wav_bytes(), "audio/wav"))],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "complete"
    assert payload["request_id"] == response.headers["x-hfs-request-id"]
    assert payload["assessment_id"] == "assessment-1"
    assert payload["analyzed_items"] == 1
    assert payload["item_results"][0]["status"] == "complete"
    assert payload["item_results"][0]["analysis"]["metrics"]["duration_seconds"] > 0
    assert payload["item_results"][0]["review_facts"]
    assert payload["item_results"][1]["status"] == "no_recording"
    assert "diagnose" in payload["clinical_notice"]
