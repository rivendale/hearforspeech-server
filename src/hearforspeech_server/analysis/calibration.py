from __future__ import annotations

from collections import defaultdict

from hearforspeech_server.schemas import (
    CalibrationProfile,
    CalibrationTargetStats,
    SpeechSoundCandidate,
    SpeechSoundReviewLabel,
)

MIN_LABELS_FOR_TARGET_ADJUSTMENT = 2
MAX_SCORE_ADJUSTMENT = 0.14


def candidate_key(target: str, word_position: str | None, error_type: str) -> str:
    return "|".join([target.strip().lower(), (word_position or "").strip().lower(), error_type])


def build_calibration_profile(labels: list[SpeechSoundReviewLabel]) -> CalibrationProfile:
    reviewed_labels = [
        label
        for label in labels
        if label.slp_decision in {"confirmed", "ruled_out"}
    ]
    by_key: dict[str, list[SpeechSoundReviewLabel]] = defaultdict(list)
    for label in reviewed_labels:
        key = candidate_key(label.target, label.word_position, label.candidate_error_type)
        by_key[key].append(label)

    target_stats: list[CalibrationTargetStats] = []
    for key, key_labels in by_key.items():
        confirmed = sum(1 for label in key_labels if label.slp_decision == "confirmed")
        ruled_out = sum(1 for label in key_labels if label.slp_decision == "ruled_out")
        total = confirmed + ruled_out
        if total == 0:
            continue

        sample = key_labels[0]
        precision_estimate = confirmed / total
        suggested_score_adjustment = 0.0
        if total >= MIN_LABELS_FOR_TARGET_ADJUSTMENT:
            suggested_score_adjustment = max(
                -MAX_SCORE_ADJUSTMENT,
                min(MAX_SCORE_ADJUSTMENT, (precision_estimate - 0.5) * 0.28),
            )

        target_stats.append(
            CalibrationTargetStats(
                key=key,
                target=sample.target,
                word_position=sample.word_position,
                error_type=sample.candidate_error_type,
                reviewed=total,
                confirmed=confirmed,
                ruled_out=ruled_out,
                precision_estimate=round(precision_estimate, 3),
                suggested_score_adjustment=round(suggested_score_adjustment, 3),
            )
        )

    target_stats.sort(
        key=lambda stat: (stat.reviewed, abs(stat.suggested_score_adjustment), stat.confirmed),
        reverse=True,
    )
    return CalibrationProfile(
        label_count=len(labels),
        reviewed_count=len(reviewed_labels),
        target_stats=target_stats[:80],
        summary=calibration_summary(len(labels), reviewed_labels, target_stats),
    )


def calibration_summary(
    label_count: int,
    reviewed_labels: list[SpeechSoundReviewLabel],
    target_stats: list[CalibrationTargetStats],
) -> str:
    if label_count == 0:
        return (
            "No SLP review labels were supplied; analyzer ranking used the default "
            "conservative profile."
        )
    if len(reviewed_labels) < MIN_LABELS_FOR_TARGET_ADJUSTMENT:
        return (
            f"{label_count} SLP review label(s) supplied. Keep labeling confirmed and ruled-out "
            "candidates before relying on target-specific ranking adjustments."
        )
    adjusted = sum(1 for stat in target_stats if stat.suggested_score_adjustment != 0)
    return (
        f"{label_count} SLP review label(s) supplied; {len(reviewed_labels)} confirmed/ruled-out "
        f"label(s) used. {adjusted} target/error pattern(s) have local ranking adjustments."
    )


def score_adjustment_for_candidate(
    candidate: SpeechSoundCandidate,
    profile: CalibrationProfile | None,
) -> float:
    if profile is None:
        return 0.0

    key = candidate_key(candidate.target, candidate.word_position, candidate.error_type)
    exact = next((stat for stat in profile.target_stats if stat.key == key), None)
    if exact is not None:
        return exact.suggested_score_adjustment

    target_matches = [
        stat
        for stat in profile.target_stats
        if stat.target == candidate.target and stat.error_type == candidate.error_type
    ]
    if not target_matches:
        return 0.0

    weighted_total = sum(stat.reviewed for stat in target_matches)
    if weighted_total < MIN_LABELS_FOR_TARGET_ADJUSTMENT:
        return 0.0
    weighted_adjustment = sum(
        stat.suggested_score_adjustment * stat.reviewed for stat in target_matches
    ) / weighted_total
    return max(-0.08, min(0.08, weighted_adjustment))


def apply_calibration_to_candidates(
    candidates: list[SpeechSoundCandidate],
    profile: CalibrationProfile | None,
) -> list[SpeechSoundCandidate]:
    if profile is None or profile.reviewed_count < MIN_LABELS_FOR_TARGET_ADJUSTMENT:
        return candidates

    adjusted_candidates: list[SpeechSoundCandidate] = []
    for candidate in candidates:
        adjustment = score_adjustment_for_candidate(candidate, profile)
        if adjustment == 0:
            adjusted_candidates.append(candidate)
            continue

        adjusted_score = max(0.0, min(1.0, candidate.score + adjustment))
        direction = "up" if adjustment > 0 else "down"
        adjusted_candidates.append(
            candidate.model_copy(
                update={
                    "score": round(adjusted_score, 3),
                    "confidence": confidence_for_score(adjusted_score),
                    "evidence": [
                        *candidate.evidence,
                        (
                            "Local SLP review labels adjusted this candidate "
                            f"{direction} by {abs(adjustment):.2f}."
                        ),
                    ],
                }
            )
        )
    return sorted(adjusted_candidates, key=lambda candidate: candidate.score, reverse=True)


def confidence_for_score(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"
