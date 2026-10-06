from statistics import mean, pstdev
from typing import Any

from app.schemas.wellbeing import WellbeingSource


def recovery_state(checkin: dict[str, Any] | None, sleep: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    factors: dict[str, Any] = {}
    normalized: list[float] = []
    if checkin:
        for field in ("recovery_feeling",):
            value = checkin.get(field)
            if isinstance(value, int):
                factors[field] = {"value": value, "source": WellbeingSource.SELF_REPORTED.value}
                normalized.append(float(value))
        for field in ("fatigue", "soreness", "stress"):
            value = checkin.get(field)
            if isinstance(value, int):
                factors[field] = {"value": value, "source": WellbeingSource.SELF_REPORTED.value}
                normalized.append(6.0 - value)
    if sleep and isinstance(sleep.get("duration_minutes"), int):
        factors["sleep_duration_minutes"] = {
            "value": sleep["duration_minutes"],
            "source": sleep.get("source", WellbeingSource.SELF_REPORTED.value),
        }
    if not normalized:
        return "INSUFFICIENT_DATA", factors
    score = mean(normalized)
    return ("GOOD" if score >= 4 else "MODERATE" if score >= 3 else "LOW"), factors


def classify_trend(values: list[float], *, higher_is_better: bool = True) -> dict[str, Any]:
    if len(values) < 3:
        return {"classification": "INSUFFICIENT_DATA", "observation_count": len(values), "direction": None}
    ordered = values if higher_is_better else [-value for value in values]
    first = mean(ordered[: max(1, len(ordered) // 3)])
    last = mean(ordered[-max(1, len(ordered) // 3) :])
    delta = last - first
    if pstdev(ordered) >= 1.0:
        classification = "VARIABLE"
    elif abs(delta) < 0.5:
        classification = "STABLE"
    else:
        classification = "IMPROVING" if delta > 0 else "DECLINING"
    return {
        "classification": classification,
        "observation_count": len(values),
        "direction": "UP" if delta > 0 else "DOWN" if delta < 0 else "UNCHANGED",
    }


def interpret_wellbeing(
    checkin: dict[str, Any] | None,
    camera_features: dict[str, Any] | None,
    sleep: dict[str, Any] | None,
    recovery: dict[str, Any] | None,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    if checkin:
        observations.extend(
            {"name": field, "value": checkin[field], "source": WellbeingSource.SELF_REPORTED.value}
            for field in ("energy", "stress", "fatigue", "soreness", "recovery_feeling")
            if isinstance(checkin.get(field), int)
        )
    if camera_features:
        observations.append(
            {
                "name": "capture_quality",
                "value": camera_features.get("capture_quality"),
                "source": WellbeingSource.CAMERA_OBSERVED.value,
            }
        )
        observations.append(
            {
                "name": "face_position_stability",
                "value": camera_features.get("face_position_stability"),
                "source": WellbeingSource.CAMERA_OBSERVED.value,
            }
        )
    if sleep:
        observations.append(
            {
                "name": "sleep_duration_minutes",
                "value": sleep.get("duration_minutes"),
                "source": sleep.get("source", WellbeingSource.SELF_REPORTED.value),
            }
        )
    return {
        "observations": observations,
        "recovery_state": recovery.get("recovery_state") if recovery else "INSUFFICIENT_DATA",
        "recovery_source": WellbeingSource.CALCULATED.value if recovery else None,
        "summary": (
            "Your recorded self-reported wellbeing and available observations are shown separately. "
            "The available information does not establish a medical or psychological diagnosis."
            if observations
            else "There is not enough recorded information to summarize wellbeing yet."
        ),
        "limitations": [
            "Camera results describe observable features, not emotional or medical states.",
            "Self-reported and camera-observed information remain distinct.",
        ],
    }
