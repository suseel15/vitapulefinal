from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CNNPrediction:
    label: str
    model_name: str
    model_version: str
    feature_schema_version: str


class OneDCNNJsonModel:
    """A compact 1D convolutional classifier exported as a JSON artifact."""

    def __init__(self, artifact: dict[str, Any], *, expected_schema: str) -> None:
        if artifact.get("feature_schema_version") != expected_schema:
            raise ValueError("Model feature schema is incompatible.")
        if artifact.get("status") != "ACTIVE":
            raise ValueError("Only an ACTIVE model may be used for athlete inference.")
        model_format = artifact.get("format")
        if model_format == "vitapulse-1d-cnn-json-v2":
            required = (
                "conv_kernels",
                "conv_biases",
                "dense_weights",
                "dense_biases",
                "normalization_mean",
                "normalization_scale",
                "feature_names",
                "classes",
            )
            if any(not artifact.get(key) for key in required):
                raise ValueError("The model artifact is incomplete.")
            filter_count = len(artifact["conv_kernels"])
            class_count = len(artifact["classes"])
            if (
                len(artifact["conv_biases"]) != filter_count
                or len(artifact["dense_weights"]) != filter_count
                or any(len(row) != class_count for row in artifact["dense_weights"])
                or len(artifact["dense_biases"]) != class_count
                or len(artifact["normalization_mean"]) != len(artifact["feature_names"])
                or len(artifact["normalization_scale"]) != len(artifact["feature_names"])
            ):
                raise ValueError("The model artifact has incompatible layer dimensions.")
        elif model_format == "vitapulse-1d-cnn-json-v1":
            if not artifact.get("conv_filters") or not artifact.get("classes"):
                raise ValueError("The model artifact is incomplete.")
        else:
            raise ValueError("The model artifact is incomplete.")
        self.artifact = artifact

    def predict(
        self,
        values: list[float],
        *,
        sampling_rate_hz: float,
        sensor_placement: str,
        quality_acceptable: bool,
    ) -> CNNPrediction | None:
        if not quality_acceptable or sampling_rate_hz < self.artifact["minimum_sampling_rate_hz"]:
            return None
        if sensor_placement not in self.artifact["supported_sensor_placements"]:
            return None
        if len(values) != len(self.artifact["feature_names"]) or not all(math.isfinite(value) for value in values):
            return None

        if self.artifact["format"] == "vitapulse-1d-cnn-json-v2":
            normalized: list[float] = [
                (float(value) - float(mean)) / float(scale)
                for value, mean, scale in zip(
                    values,
                    self.artifact["normalization_mean"],
                    self.artifact["normalization_scale"],
                    strict=True,
                )
            ]
            kernel_bank = self.artifact["conv_kernels"]
            kernel_size = len(kernel_bank[0])
            pooled: list[float] = []
            for kernel, bias in zip(kernel_bank, self.artifact["conv_biases"], strict=True):
                responses: list[float] = []
                for start in range(len(normalized) - kernel_size + 1):
                    response = sum(
                        normalized[start + offset] * float(weight)
                        for offset, weight in enumerate(kernel)
                    ) + float(bias)
                    responses.append(response)
                response = max(responses, default=0.0)
                pooled.append(response)
            class_scores: list[float] = [
                sum(
                    pooled[filter_index] * float(self.artifact["dense_weights"][filter_index][class_index])
                    for filter_index in range(len(pooled))
                ) + float(self.artifact["dense_biases"][class_index])
                for class_index in range(len(self.artifact["classes"]))
            ]
            best_label = self.artifact["classes"][max(range(len(class_scores)), key=class_scores.__getitem__)]
        else:
            scores: dict[str, float] = {}
            for label in self.artifact["classes"]:
                kernel_bank = self.artifact["conv_filters"].get(label, [])
                if not kernel_bank:
                    continue
                score = float(self.artifact.get("class_biases", {}).get(label, 0.0))
                for kernel in kernel_bank:
                    score += _conv_score(values, kernel)
                scores[label] = score
            if not scores:
                return None
            best_label = max(scores.items(), key=lambda item: item[1])[0]
        return CNNPrediction(
            label=best_label,
            model_name=self.artifact["model_name"],
            model_version=self.artifact["model_version"],
            feature_schema_version=self.artifact["feature_schema_version"],
        )


def _conv_score(values: list[float], kernel: list[float]) -> float:
    if not kernel:
        return 0.0
    kernel_len = len(kernel)
    if kernel_len > len(values):
        return 0.0
    contributions: list[float] = []
    for start in range(len(values) - kernel_len + 1):
        dot = 0.0
        for offset, weight in enumerate(kernel):
            dot += values[start + offset] * weight
        contributions.append(dot)
    return max(contributions) if contributions else 0.0
