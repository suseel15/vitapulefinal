from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class ForestPrediction:
    label: str
    model_name: str
    model_version: str
    feature_schema_version: str


class RandomForestJsonModel:
    """Inference for the JSON tree format emitted by training/export.py."""

    def __init__(self, artifact: dict[str, Any], *, expected_schema: str) -> None:
        if artifact.get("feature_schema_version") != expected_schema:
            raise ValueError("Model feature schema is incompatible.")
        if artifact.get("status") != "ACTIVE":
            raise ValueError("Only an ACTIVE model may be used for athlete inference.")
        if not artifact.get("trees") or not artifact.get("classes"):
            raise ValueError("The model artifact is incomplete.")
        self.artifact = artifact

    def predict(
        self,
        values: list[float],
        *,
        sampling_rate_hz: float,
        sensor_placement: str,
        quality_acceptable: bool,
    ) -> ForestPrediction | None:
        if not quality_acceptable or sampling_rate_hz < self.artifact["minimum_sampling_rate_hz"]:
            return None
        if sensor_placement not in self.artifact["supported_sensor_placements"]:
            return None
        if len(values) != len(self.artifact["feature_names"]) or not all(math.isfinite(value) for value in values):
            return None
        votes: Counter[str] = Counter()
        for tree in self.artifact["trees"]:
            votes[_tree_label(tree, values)] += 1
        label = min(votes, key=lambda candidate: (-votes[candidate], candidate))
        return ForestPrediction(
            label=label,
            model_name=self.artifact["model_name"],
            model_version=self.artifact["model_version"],
            feature_schema_version=self.artifact["feature_schema_version"],
        )


def _tree_label(node: dict[str, Any], values: list[float]) -> str:
    while "class" not in node:
        index = node["feature_index"]
        node = node["left"] if values[index] <= node["threshold"] else node["right"]
    return str(node["class"])
