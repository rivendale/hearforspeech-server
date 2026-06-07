from __future__ import annotations

import re
import shutil
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from pathlib import Path
from uuid import uuid4

from hearforspeech_server.analysis.pipeline import (
    CLINICAL_NOTICE,
    analyze_recording,
    build_review_facts,
)
from hearforspeech_server.schemas import (
    AcousticMetrics,
    AnalysisFact,
    EngineInfo,
    SpeechSoundAnalysisResult,
    SpeechSoundCandidate,
)

WORD_TARGETS: dict[str, str] = {
    "red": "/r/",
    "rabbit": "/r/",
    "ring": "/r/",
    "rain": "/r/",
    "car": "/r/",
    "star": "/r/",
    "bird": "/r/",
    "girl": "/r/",
    "teacher": "/r/",
    "mother": "/r/",
    "world": "/r/",
    "sun": "/s/",
    "soup": "/s/",
    "science": "/s/",
    "bus": "/s/",
    "class": "/s/",
    "zoo": "/z/",
    "zebra": "/z/",
    "busy": "/z/",
    "buzz": "/z/",
    "shoe": "/ʃ/",
    "shop": "/ʃ/",
    "fish": "/ʃ/",
    "chair": "/tʃ/",
    "watch": "/tʃ/",
    "jump": "/dʒ/",
    "bridge": "/dʒ/",
    "thin": "/θ/",
    "thumb": "/θ/",
    "teeth": "/θ/",
    "this": "/ð/",
    "they": "/ð/",
}

CLUSTER_WORDS = {
    "spoon",
    "star",
    "skate",
    "smile",
    "snake",
    "swim",
    "slide",
    "prize",
    "break",
    "tree",
    "drive",
    "crown",
    "green",
    "frog",
    "play",
    "blue",
    "clean",
    "glue",
    "fly",
    "sleep",
    "queen",
    "twelve",
    "dwell",
    "best",
    "hand",
    "milk",
    "left",
    "asked",
    "desks",
    "texts",
    "lamps",
}

PHONE_ALIASES: dict[str, set[str]] = {
    "/r/": {"r", "ɹ", "ɚ", "ɝ"},
    "/s/": {"s"},
    "/z/": {"z"},
    "/ʃ/": {"ʃ", "sh"},
    "/tʃ/": {"tʃ", "ch"},
    "/dʒ/": {"dʒ", "jh", "j"},
    "/θ/": {"θ", "th"},
    "/ð/": {"ð", "dh"},
}


def allosaurus_engine_info() -> EngineInfo:
    if find_spec("allosaurus") is None:
        return EngineInfo(
            name="allosaurus",
            available=False,
            note="Install allosaurus for beta phone-candidate output.",
        )

    try:
        package_version = version("allosaurus")
    except PackageNotFoundError:
        package_version = None

    return EngineInfo(
        name="allosaurus",
        available=True,
        version=package_version,
        note="Beta exploratory phone-candidate output; SLP review required.",
    )


def mfa_engine_info() -> EngineInfo:
    executable = shutil.which("mfa")
    return EngineInfo(
        name="mfa",
        available=bool(executable),
        note=(
            "Montreal Forced Aligner executable found; scripted prompt alignment can be "
            "enabled when acoustic models/dictionaries are configured."
            if executable
            else (
                "Install Montreal Forced Aligner plus acoustic models/dictionaries for "
                "forced alignment."
            )
        ),
    )


def extract_prompt_words(prompt_text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]+(?:'[a-z]+)?", prompt_text.lower())


def expected_targets_from_prompt(prompt_text: str) -> list[str]:
    prompt_lower = prompt_text.lower()
    explicit_targets = re.findall(r"/[^/\s]+/", prompt_lower)
    prompt_words = extract_prompt_words(prompt_text)
    word_targets = [WORD_TARGETS[word] for word in prompt_words if word in WORD_TARGETS]
    if any(word in CLUSTER_WORDS for word in prompt_words):
        word_targets.append("clusters")
    return list(dict.fromkeys([*explicit_targets, *word_targets]))


def recognize_phone_candidates(path: Path) -> tuple[list[str], list[str]]:
    if not allosaurus_engine_info().available:
        return [], ["Allosaurus is unavailable; phone candidates were not generated."]

    try:
        from allosaurus.app import read_recognizer  # type: ignore[import-not-found]

        recognizer = read_recognizer()
        raw_output = recognizer.recognize(str(path))
    except Exception as exc:  # pragma: no cover - optional engine unavailable in CI
        return [], [f"Allosaurus phone-candidate recognition failed: {exc.__class__.__name__}."]

    phones = [phone.strip() for phone in re.split(r"\s+", raw_output) if phone.strip()]
    return phones, []


def phone_candidate_for_target(target: str, phones: list[str]) -> str | None:
    aliases = PHONE_ALIASES.get(target, {target.strip("/")})
    phone_set = {phone.lower() for phone in phones}
    return next((phone for phone in phone_set if phone in aliases), None)


def build_candidate(
    *,
    target: str,
    expected: str | None,
    observed: str | None,
    error_type: str,
    confidence: str,
    evidence: list[str],
    review_prompt: str,
) -> SpeechSoundCandidate:
    return SpeechSoundCandidate(
        target=target,
        expected=expected,
        observed=observed,
        error_type=error_type,
        confidence=confidence,
        evidence=evidence,
        review_prompt=review_prompt,
    )


def rough_acoustic_candidates(
    metrics: AcousticMetrics | None,
    expected_targets: list[str],
    phone_candidates: list[str],
) -> list[SpeechSoundCandidate]:
    candidates: list[SpeechSoundCandidate] = []
    if metrics is None:
        return [
            build_candidate(
                target="speech sample",
                expected=None,
                observed=None,
                error_type="needs_review",
                confidence="low",
                evidence=["Acoustic metrics were unavailable."],
                review_prompt="Replay the sample and complete SLP sound inventory scoring.",
            )
        ]

    has_phone_candidates = bool(phone_candidates)
    for target in expected_targets:
        if target == "clusters":
            candidates.append(
                build_candidate(
                    target="clusters",
                    expected="cluster retained",
                    observed=None,
                    error_type="possible_cluster_reduction",
                    confidence="medium" if has_phone_candidates else "low",
                    evidence=[
                        "Prompt includes consonant clusters.",
                        "Review whether all cluster elements are present in the recording.",
                    ],
                    review_prompt="Listen for cluster reduction, sequencing errors, or distortion.",
                )
            )
            continue

        observed_phone = phone_candidate_for_target(target, phone_candidates)
        if has_phone_candidates and observed_phone is None:
            candidates.append(
                build_candidate(
                    target=target,
                    expected=target,
                    observed="not present in phone candidates",
                    error_type="possible_omission",
                    confidence="medium",
                    evidence=[
                        f"Allosaurus phone candidates did not include an alias for {target}.",
                        (
                            "Phone recognizer output is beta and can be wrong; SLP "
                            "confirmation required."
                        ),
                    ],
                    review_prompt=(
                        f"Replay the target and confirm whether {target} was omitted, "
                        "substituted, or distorted."
                    ),
                )
            )
            continue

        if target in {"/s/", "/z/", "/ʃ/", "/tʃ/", "/dʒ/"}:
            evidence = ["Prompt includes sibilant/affricate targets."]
            if metrics.zero_crossing_rate is not None and metrics.zero_crossing_rate < 800:
                evidence.append(
                    f"Zero-crossing rate was {metrics.zero_crossing_rate:.1f}/sec, "
                    "which may be low for strong frication."
                )
            candidates.append(
                build_candidate(
                    target=target,
                    expected=target,
                    observed=observed_phone,
                    error_type="possible_distortion",
                    confidence="medium" if has_phone_candidates else "low",
                    evidence=evidence,
                    review_prompt=(
                        "Listen for frontal/lateral distortion, substitution, or weak "
                        f"frication on {target}."
                    ),
                )
            )
        elif target in {"/r/", "/θ/", "/ð/"}:
            candidates.append(
                build_candidate(
                    target=target,
                    expected=target,
                    observed=observed_phone,
                    error_type="possible_distortion",
                    confidence="medium" if has_phone_candidates else "low",
                    evidence=[
                        f"Prompt includes residual adolescent target {target}.",
                        "Residual sound errors require clinician auditory-perceptual review.",
                    ],
                    review_prompt=(
                        f"Replay the target words and confirm whether {target} is clear, "
                        "distorted, substituted, or omitted."
                    ),
                )
            )

    word_count = max(1, len(expected_targets))
    if metrics.duration_seconds < 0.75 and word_count >= 2:
        candidates.append(
            build_candidate(
                target="sample duration",
                expected="complete production",
                observed=f"{metrics.duration_seconds:.2f} seconds",
                error_type="possible_omission",
                confidence="low",
                evidence=["Recording may be too short for the expected prompt."],
                review_prompt=(
                    "Check whether the patient completed the prompt or the recording "
                    "stopped early."
                ),
            )
        )

    if metrics.voiced_fraction is not None and metrics.voiced_fraction < 0.2:
        candidates.append(
            build_candidate(
                target="intelligibility",
                expected="voiced speech present",
                observed=f"voiced fraction {metrics.voiced_fraction:.2f}",
                error_type="possible_rate_or_intelligibility",
                confidence="low",
                evidence=[
                    "Low voiced fraction may reflect silence, noise, whispering, or "
                    "recording quality."
                ],
                review_prompt=(
                    "Check recording quality, volume, and whether speech is captured "
                    "clearly."
                ),
            )
        )

    return candidates[:12]


def analyze_speech_sound_patterns(
    path: Path,
    *,
    prompt_text: str,
    filename: str,
    content_type: str | None,
) -> SpeechSoundAnalysisResult:
    acoustic = analyze_recording(
        path,
        prompt_text=prompt_text,
        filename=filename,
        content_type=content_type,
    )
    phone_candidates, phone_warnings = recognize_phone_candidates(path)
    expected_targets = expected_targets_from_prompt(prompt_text)
    possible_errors = rough_acoustic_candidates(
        acoustic.metrics,
        expected_targets,
        phone_candidates,
    )
    engines = [acoustic.engine, allosaurus_engine_info(), mfa_engine_info()]
    review_facts: list[AnalysisFact] = [
        *build_review_facts(acoustic.metrics, acoustic.engine),
        AnalysisFact(
            label="Expected speech targets",
            value=", ".join(expected_targets) if expected_targets else "not parsed from prompt",
            source="prompt-parser",
            caution="Use scripted prompts for stronger target parsing.",
        ),
    ]
    if phone_candidates:
        review_facts.append(
            AnalysisFact(
                label="Allosaurus phone candidates",
                value=" ".join(phone_candidates[:40]),
                source="allosaurus",
                caution="Beta exploratory output; may be inaccurate.",
            )
        )

    warnings = [*acoustic.warnings, *phone_warnings]
    if not expected_targets:
        warnings.append(
            "No expected target phones were parsed; provide scripted words or /phoneme/ "
            "targets."
        )

    summary = (
        f"Speech-sound review generated {len(possible_errors)} possible pattern(s) for SLP review. "
        "Candidates are not diagnoses; confirm by replaying the recording and scoring "
        "the target sounds."
    )

    return SpeechSoundAnalysisResult(
        job_id=str(uuid4()),
        status="complete",
        prompt_text=prompt_text,
        filename=filename,
        content_type=content_type,
        engines=engines,
        metrics=acoustic.metrics,
        possible_errors=possible_errors,
        review_facts=review_facts,
        warnings=warnings,
        clinician_summary=summary,
        clinical_notice=CLINICAL_NOTICE,
    )
