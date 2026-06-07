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


def test_capabilities() -> None:
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "hearforspeech-server"
    assert "POST /v1/analysis/parselmouth" in payload["endpoints"]


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
    assert "diagnose" in payload["clinical_notice"]
