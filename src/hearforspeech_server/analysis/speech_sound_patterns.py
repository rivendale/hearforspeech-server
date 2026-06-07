from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from pathlib import Path
from typing import Literal
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

SpeechErrorType = Literal[
    "possible_substitution",
    "possible_omission",
    "possible_distortion",
    "possible_cluster_reduction",
    "possible_rate_or_intelligibility",
    "needs_review",
]
CandidateConfidence = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class TargetOccurrence:
    word: str
    target: str
    word_position: str
    category: str


PHONE_ALIASES: dict[str, set[str]] = {
    "/p/": {"p"},
    "/b/": {"b"},
    "/t/": {"t"},
    "/d/": {"d"},
    "/k/": {"k"},
    "/g/": {"g"},
    "/m/": {"m"},
    "/n/": {"n"},
    "/ŋ/": {"ŋ", "ng"},
    "/f/": {"f"},
    "/v/": {"v"},
    "/r/": {"r", "ɹ", "ɚ", "ɝ"},
    "/l/": {"l"},
    "/s/": {"s"},
    "/z/": {"z"},
    "/ʃ/": {"ʃ", "sh"},
    "/ʒ/": {"ʒ", "zh"},
    "/tʃ/": {"tʃ", "ch"},
    "/dʒ/": {"dʒ", "jh", "j"},
    "/θ/": {"θ", "th"},
    "/ð/": {"ð", "dh"},
    "/w/": {"w"},
    "/j/": {"j", "y"},
}

LIKELY_SUBSTITUTES: dict[str, set[str]] = {
    "/r/": {"w", "l", "ə", "ɚ", "ɝ"},
    "/l/": {"w", "j"},
    "/s/": {"θ", "ʃ", "t", "f"},
    "/z/": {"s", "d", "ð", "v"},
    "/ʃ/": {"s", "tʃ"},
    "/ʒ/": {"ʃ", "z", "dʒ"},
    "/tʃ/": {"ʃ", "t", "ts"},
    "/dʒ/": {"ʒ", "d", "z"},
    "/θ/": {"f", "t", "s"},
    "/ð/": {"d", "v", "z"},
}

SIBILANT_TARGETS = {"/s/", "/z/", "/ʃ/", "/ʒ/", "/tʃ/", "/dʒ/"}
RESIDUAL_TARGETS = {"/r/", "/s/", "/z/", "/ʃ/", "/ʒ/", "/tʃ/", "/dʒ/", "/θ/", "/ð/"}


def target(word: str, sound: str, position: str, category: str = "consonant") -> TargetOccurrence:
    return TargetOccurrence(word=word, target=sound, word_position=position, category=category)


INVENTORY_TARGETS: dict[str, list[TargetOccurrence]] = {
    "pie": [target("pie", "/p/", "initial")],
    "boy": [target("boy", "/b/", "initial")],
    "tie": [target("tie", "/t/", "initial")],
    "day": [target("day", "/d/", "initial")],
    "key": [target("key", "/k/", "initial")],
    "go": [target("go", "/g/", "initial")],
    "me": [target("me", "/m/", "initial")],
    "no": [target("no", "/n/", "initial")],
    "fan": [target("fan", "/f/", "initial")],
    "van": [target("van", "/v/", "initial")],
    "thin": [target("thin", "/θ/", "initial", "residual consonant")],
    "this": [target("this", "/ð/", "initial", "residual consonant")],
    "sun": [target("sun", "/s/", "initial", "sibilant")],
    "zoo": [target("zoo", "/z/", "initial", "sibilant")],
    "shoe": [target("shoe", "/ʃ/", "initial", "sibilant")],
    "chair": [target("chair", "/tʃ/", "initial", "affricate")],
    "jump": [target("jump", "/dʒ/", "initial", "affricate")],
    "light": [target("light", "/l/", "initial")],
    "red": [target("red", "/r/", "initial", "residual consonant")],
    "we": [target("we", "/w/", "initial")],
    "yes": [target("yes", "/j/", "initial")],
    "rabbit": [target("rabbit", "/r/", "initial", "residual consonant")],
    "ring": [target("ring", "/r/", "initial", "residual consonant")],
    "rain": [target("rain", "/r/", "initial", "residual consonant")],
    "apple": [target("apple", "/p/", "medial")],
    "butter": [target("butter", "/t/", "medial")],
    "ladder": [target("ladder", "/d/", "medial")],
    "soccer": [target("soccer", "/k/", "medial")],
    "tiger": [target("tiger", "/g/", "medial")],
    "hammer": [target("hammer", "/m/", "medial")],
    "pony": [target("pony", "/n/", "medial")],
    "singing": [target("singing", "/ŋ/", "medial")],
    "dolphin": [target("dolphin", "/f/", "medial")],
    "seven": [target("seven", "/v/", "medial")],
    "birthday": [target("birthday", "/θ/", "medial", "residual consonant")],
    "mother": [
        target("mother", "/ð/", "medial", "residual consonant"),
        target("mother", "/r/", "final/vocalic", "residual consonant"),
    ],
    "pencil": [target("pencil", "/s/", "medial", "sibilant")],
    "busy": [target("busy", "/z/", "medial", "sibilant")],
    "fishing": [target("fishing", "/ʃ/", "medial", "sibilant")],
    "measure": [target("measure", "/ʒ/", "medial", "sibilant")],
    "teacher": [
        target("teacher", "/tʃ/", "medial", "affricate"),
        target("teacher", "/r/", "final/vocalic", "residual consonant"),
    ],
    "magic": [target("magic", "/dʒ/", "medial", "affricate")],
    "yellow": [target("yellow", "/l/", "medial")],
    "carrot": [target("carrot", "/r/", "medial", "residual consonant")],
    "canyon": [target("canyon", "/j/", "medial")],
    "cup": [target("cup", "/p/", "final")],
    "tub": [target("tub", "/b/", "final")],
    "cat": [target("cat", "/t/", "final")],
    "bed": [target("bed", "/d/", "final")],
    "book": [target("book", "/k/", "final")],
    "dog": [target("dog", "/g/", "final")],
    "home": [target("home", "/m/", "final")],
    "moon": [target("moon", "/n/", "final")],
    "leaf": [target("leaf", "/f/", "final")],
    "five": [target("five", "/v/", "final")],
    "teeth": [target("teeth", "/θ/", "final", "residual consonant")],
    "bathe": [target("bathe", "/ð/", "final", "residual consonant")],
    "bus": [target("bus", "/s/", "final", "sibilant")],
    "buzz": [target("buzz", "/z/", "final", "sibilant")],
    "fish": [target("fish", "/ʃ/", "final", "sibilant")],
    "garage": [target("garage", "/ʒ/", "final", "sibilant")],
    "watch": [target("watch", "/tʃ/", "final", "affricate")],
    "bridge": [target("bridge", "/dʒ/", "final", "affricate")],
    "ball": [target("ball", "/l/", "final")],
    "car": [target("car", "/r/", "final/vocalic", "residual consonant")],
    "star": [
        target("star", "clusters", "initial cluster", "cluster"),
        target("star", "/s/", "initial cluster", "sibilant"),
        target("star", "/r/", "final/vocalic", "residual consonant"),
    ],
    "bird": [target("bird", "/r/", "vocalic", "residual consonant")],
    "girl": [target("girl", "/r/", "vocalic", "residual consonant")],
    "world": [target("world", "/r/", "vocalic", "residual consonant")],
    "street": [target("street", "clusters", "initial cluster", "cluster")],
    "tree": [
        target("tree", "clusters", "initial cluster", "cluster"),
        target("tree", "/r/", "initial cluster", "residual consonant"),
    ],
    "spoon": [target("spoon", "clusters", "initial cluster", "cluster")],
    "skate": [target("skate", "clusters", "initial cluster", "cluster")],
    "smile": [target("smile", "clusters", "initial cluster", "cluster")],
    "snake": [target("snake", "clusters", "initial cluster", "cluster")],
    "swim": [target("swim", "clusters", "initial cluster", "cluster")],
    "slide": [target("slide", "clusters", "initial cluster", "cluster")],
    "prize": [target("prize", "clusters", "initial cluster", "cluster")],
    "break": [target("break", "clusters", "initial cluster", "cluster")],
    "drive": [target("drive", "clusters", "initial cluster", "cluster")],
    "crown": [target("crown", "clusters", "initial cluster", "cluster")],
    "green": [target("green", "clusters", "initial cluster", "cluster")],
    "frog": [target("frog", "clusters", "initial cluster", "cluster")],
    "play": [target("play", "clusters", "initial cluster", "cluster")],
    "blue": [target("blue", "clusters", "initial cluster", "cluster")],
    "clean": [target("clean", "clusters", "initial cluster", "cluster")],
    "glue": [target("glue", "clusters", "initial cluster", "cluster")],
    "fly": [target("fly", "clusters", "initial cluster", "cluster")],
    "sleep": [target("sleep", "clusters", "initial cluster", "cluster")],
    "queen": [target("queen", "clusters", "initial cluster", "cluster")],
    "twelve": [target("twelve", "clusters", "initial cluster", "cluster")],
    "dwell": [target("dwell", "clusters", "initial cluster", "cluster")],
    "best": [target("best", "clusters", "final cluster", "cluster")],
    "hand": [target("hand", "clusters", "final cluster", "cluster")],
    "milk": [target("milk", "clusters", "final cluster", "cluster")],
    "left": [target("left", "clusters", "final cluster", "cluster")],
    "asked": [target("asked", "clusters", "final cluster", "cluster")],
    "desks": [target("desks", "clusters", "final cluster", "cluster")],
    "texts": [target("texts", "clusters", "final cluster", "cluster")],
    "lamps": [target("lamps", "clusters", "final cluster", "cluster")],
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


def target_occurrences_from_prompt(prompt_text: str) -> list[TargetOccurrence]:
    prompt_lower = prompt_text.lower()
    explicit_targets = [
        TargetOccurrence(
            word=target_text,
            target=target_text,
            word_position="explicit",
            category="explicit target",
        )
        for target_text in re.findall(r"/[^/\s]+/", prompt_lower)
    ]
    prompt_words = extract_prompt_words(prompt_text)
    word_targets = [
        occurrence
        for word in prompt_words
        for occurrence in INVENTORY_TARGETS.get(word, [])
    ]
    unique: dict[tuple[str, str, str], TargetOccurrence] = {}
    for occurrence in [*explicit_targets, *word_targets]:
        unique[(occurrence.word, occurrence.target, occurrence.word_position)] = occurrence
    return list(unique.values())


def expected_targets_from_prompt(prompt_text: str) -> list[str]:
    return list(dict.fromkeys(item.target for item in target_occurrences_from_prompt(prompt_text)))


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
    phone_set = normalize_phone_set(phones)
    return next((phone for phone in phone_set if phone in aliases), None)


def normalize_phone_set(phones: list[str]) -> set[str]:
    return {phone.lower().strip("ˈˌ:ː") for phone in phones if phone.strip()}


def substitute_candidate_for_target(target: str, phones: list[str]) -> str | None:
    substitutes = LIKELY_SUBSTITUTES.get(target, set())
    phone_set = normalize_phone_set(phones)
    return next((phone for phone in phone_set if phone in substitutes), None)


def confidence_for_score(score: float) -> CandidateConfidence:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def build_candidate(
    *,
    target: str,
    expected: str | None,
    observed: str | None,
    error_type: SpeechErrorType,
    score: float,
    evidence: list[str],
    review_prompt: str,
    target_word: str | None = None,
    word_position: str | None = None,
    category: str | None = None,
) -> SpeechSoundCandidate:
    return SpeechSoundCandidate(
        target=target,
        target_word=target_word,
        word_position=word_position,
        category=category,
        expected=expected,
        observed=observed,
        error_type=error_type,
        confidence=confidence_for_score(score),
        score=round(score, 3),
        evidence=evidence,
        review_prompt=review_prompt,
    )


def occurrence_review_prompt(occurrence: TargetOccurrence, default: str) -> str:
    if occurrence.word and occurrence.word != occurrence.target:
        return f"Replay “{occurrence.word}” and {default}"
    return default


def rough_acoustic_candidates(
    metrics: AcousticMetrics | None,
    expected_occurrences: list[TargetOccurrence],
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
                score=0.2,
                evidence=["Acoustic metrics were unavailable."],
                review_prompt="Replay the sample and complete SLP sound inventory scoring.",
            )
        ]

    has_phone_candidates = bool(phone_candidates)
    seen_candidate_keys: set[tuple[str, str | None, str]] = set()

    for occurrence in expected_occurrences:
        candidate_key = (occurrence.target, occurrence.word, occurrence.word_position)
        if candidate_key in seen_candidate_keys:
            continue
        seen_candidate_keys.add(candidate_key)

        if occurrence.target == "clusters":
            score = 0.5 if has_phone_candidates else 0.28
            error_type: SpeechErrorType = (
                "possible_cluster_reduction" if has_phone_candidates else "needs_review"
            )
            candidates.append(
                build_candidate(
                    target="clusters",
                    target_word=occurrence.word,
                    word_position=occurrence.word_position,
                    category=occurrence.category,
                    expected="cluster retained",
                    observed=None,
                    error_type=error_type,
                    score=score,
                    evidence=[
                        f"Prompt includes cluster word “{occurrence.word}”.",
                        (
                            "Phone candidates are available for review."
                            if has_phone_candidates
                            else "No phone candidates available; use auditory review."
                        ),
                    ],
                    review_prompt=occurrence_review_prompt(
                        occurrence,
                        "listen for cluster reduction, sequencing errors, or distortion.",
                    ),
                )
            )
            continue

        observed_phone = phone_candidate_for_target(occurrence.target, phone_candidates)
        substitute_phone = substitute_candidate_for_target(occurrence.target, phone_candidates)
        if has_phone_candidates and observed_phone is None:
            error_type = "possible_substitution" if substitute_phone else "possible_omission"
            score = 0.82 if substitute_phone else 0.68
            candidates.append(
                build_candidate(
                    target=occurrence.target,
                    target_word=occurrence.word,
                    word_position=occurrence.word_position,
                    category=occurrence.category,
                    expected=occurrence.target,
                    observed=substitute_phone or "not present in phone candidates",
                    error_type=error_type,
                    score=score,
                    evidence=[
                        (
                            "Allosaurus phone candidates did not include an alias for "
                            f"{occurrence.target}."
                        ),
                        (
                            f"Likely substitute candidate {substitute_phone} was present."
                            if substitute_phone
                            else "No common substitute phone was found in the candidate list."
                        ),
                    ],
                    review_prompt=occurrence_review_prompt(
                        occurrence,
                        (
                            f"confirm whether {occurrence.target} was omitted, "
                            "substituted, or distorted."
                        ),
                    ),
                )
            )
            continue

        if occurrence.target in SIBILANT_TARGETS:
            evidence = [
                f"Prompt includes {occurrence.category} target {occurrence.target}.",
            ]
            score = 0.22
            if metrics.zero_crossing_rate is not None and metrics.zero_crossing_rate < 900:
                evidence.append(
                    f"Zero-crossing rate was {metrics.zero_crossing_rate:.1f}/sec, "
                    "which may be low for strong sibilant frication."
                )
                score += 0.32
            if has_phone_candidates and observed_phone:
                evidence.append(f"Phone candidate list included expected {observed_phone}.")
                score -= 0.12
            if score >= 0.35:
                candidates.append(
                    build_candidate(
                        target=occurrence.target,
                        target_word=occurrence.word,
                        word_position=occurrence.word_position,
                        category=occurrence.category,
                        expected=occurrence.target,
                        observed=observed_phone,
                        error_type="possible_distortion",
                        score=max(0.25, min(score, 0.78)),
                        evidence=evidence,
                        review_prompt=occurrence_review_prompt(
                            occurrence,
                            (
                                "listen for frontal/lateral distortion, substitution, "
                                "or weak frication."
                            ),
                        ),
                    )
                )
            continue

        if occurrence.target in RESIDUAL_TARGETS:
            evidence = [
                f"Prompt includes residual adolescent target {occurrence.target}.",
            ]
            score = 0.32
            error_type = "needs_review"
            if has_phone_candidates and observed_phone:
                evidence.append(f"Phone candidate list included expected {observed_phone}.")
                score = 0.18
            elif has_phone_candidates:
                error_type = "possible_distortion"
                score = 0.62
            if score >= 0.25:
                candidates.append(
                    build_candidate(
                        target=occurrence.target,
                        target_word=occurrence.word,
                        word_position=occurrence.word_position,
                        category=occurrence.category,
                        expected=occurrence.target,
                        observed=observed_phone,
                        error_type=error_type,
                        score=score,
                        evidence=evidence,
                        review_prompt=occurrence_review_prompt(
                            occurrence,
                            (
                                f"confirm whether {occurrence.target} is clear, "
                                "distorted, substituted, or omitted."
                            ),
                        ),
                    )
                )

    word_count = max(1, len(expected_occurrences))
    if metrics.duration_seconds < 0.75 and word_count >= 2:
        candidates.append(
            build_candidate(
                target="sample duration",
                expected="complete production",
                observed=f"{metrics.duration_seconds:.2f} seconds",
                error_type="possible_omission",
                score=0.38,
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
                score=0.42,
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

    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)[:12]


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
    expected_occurrences = target_occurrences_from_prompt(prompt_text)
    expected_targets = list(dict.fromkeys(item.target for item in expected_occurrences))
    possible_errors = rough_acoustic_candidates(
        acoustic.metrics,
        expected_occurrences,
        phone_candidates,
    )
    engines = [acoustic.engine, allosaurus_engine_info(), mfa_engine_info()]
    review_facts: list[AnalysisFact] = [
        *build_review_facts(acoustic.metrics, acoustic.engine),
        AnalysisFact(
            label="Expected speech targets",
            value=(
                ", ".join(
                    f"{item.word}:{item.target}/{item.word_position}"
                    for item in expected_occurrences[:30]
                )
                if expected_occurrences
                else "not parsed from prompt"
            ),
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
