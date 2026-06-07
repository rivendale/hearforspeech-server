from pathlib import Path
from shutil import which
from subprocess import CalledProcessError, run
from tempfile import NamedTemporaryFile


def extension_for_upload(filename: str | None, content_type: str | None) -> str:
    if filename and "." in filename:
        suffix = Path(filename).suffix.lower()
        if suffix:
            return suffix
    if content_type == "audio/wav":
        return ".wav"
    if content_type == "audio/webm":
        return ".webm"
    if content_type == "audio/mpeg":
        return ".mp3"
    if content_type == "audio/mp4":
        return ".m4a"
    return ".audio"


def convert_to_wav_if_needed(input_path: Path) -> tuple[Path, list[Path], list[str]]:
    if input_path.suffix.lower() == ".wav":
        return input_path, [], []

    warnings: list[str] = []
    temp_paths: list[Path] = []
    if not which("ffmpeg"):
        warnings.append("ffmpeg is not installed; non-WAV audio may not be readable.")
        return input_path, temp_paths, warnings

    with NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        output_path = Path(temp_file.name)
    temp_paths.append(output_path)

    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_path),
    ]
    try:
        run(command, check=True)
    except CalledProcessError:
        warnings.append("ffmpeg could not convert the upload; analysis will use the original file.")
        return input_path, temp_paths, warnings

    return output_path, temp_paths, warnings
