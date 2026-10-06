package app.vitapulse.android.movement.features

import app.vitapulse.android.core.device.MovementSample
import kotlin.math.sqrt

const val FEATURE_SCHEMA_VERSION = "movement-features-v1"
val MOVEMENT_FEATURE_NAMES = buildList {
    listOf("ax", "ay", "az", "gx", "gy", "gz").forEach { axis ->
        listOf("mean", "std", "min", "max", "range").forEach { stat -> add("${axis}_${stat}") }
    }
    addAll(
        listOf(
            "acc_magnitude_mean", "acc_magnitude_std", "acc_magnitude_rms", "acc_magnitude_peak",
            "gyro_magnitude_mean", "gyro_magnitude_std", "gyro_magnitude_peak",
            "dynamic_acceleration_rms", "peak_count", "mean_peak_spacing_ms", "movement_duration_ms",
            "cadence_hz", "sampling_rate_hz", "sample_count", "missing_sample_percentage",
        ),
    )
}

data class MovementFeatures(
    val names: List<String>,
    val values: FloatArray,
    val samplingRateHz: Double,
    val sampleCount: Int,
) {
    init {
        require(names.size == values.size)
        require(values.all(Float::isFinite))
    }
}

class MovementFeatureExtractor {
    fun extract(samples: List<MovementSample>, expectedRateHz: Double = 10.0): MovementFeatures? {
        if (samples.size < 2 || expectedRateHz <= 0 || !expectedRateHz.isFinite()) return null
        val ordered = samples.sortedBy { it.appTimestamp }
        if (ordered != samples || ordered.zipWithNext().any { (a, b) -> b.appTimestamp <= a.appTimestamp }) return null
        val timestamps = samples.map { it.appTimestamp.toDouble() }
        val duration = timestamps.last() - timestamps.first()
        if (duration <= 0) return null
        val axes = listOf(
            samples.map { it.ax }, samples.map { it.ay }, samples.map { it.az },
            samples.map { it.gx }, samples.map { it.gy }, samples.map { it.gz },
        )
        if (axes.flatten().any { !it.isFinite() }) return null
        val features = mutableListOf<Double>()
        axes.forEach { values ->
            val average = values.average()
            val minimum = values.min()
            val maximum = values.max()
            features += listOf(average, standardDeviation(values), minimum, maximum, maximum - minimum)
        }
        val accMagnitude = samples.map { it.accelerationMagnitude }
        val gyroMagnitude = samples.map { it.gyroscopeMagnitude }
        val magnitudeMean = accMagnitude.average()
        val centered = accMagnitude.map { it - magnitudeMean }
        val peaks = (1 until accMagnitude.lastIndex).filter { index ->
            accMagnitude[index] > accMagnitude[index - 1] &&
                accMagnitude[index] >= accMagnitude[index + 1] &&
                accMagnitude[index] >= magnitudeMean + 0.08
        }
        val spacings = peaks.zipWithNext().map { (left, right) -> timestamps[right] - timestamps[left] }
        val rate = (samples.size - 1) * 1000.0 / duration
        features += listOf(
            magnitudeMean,
            standardDeviation(accMagnitude),
            sqrt(accMagnitude.map { it * it }.average()),
            accMagnitude.max(),
            gyroMagnitude.average(),
            standardDeviation(gyroMagnitude),
            gyroMagnitude.max(),
            sqrt(centered.map { it * it }.average()),
            peaks.size.toDouble(),
            spacings.average().takeIf { spacings.isNotEmpty() } ?: 0.0,
            duration,
            spacings.average().let { if (spacings.isNotEmpty() && it > 0) 1000.0 / it else 0.0 },
            rate,
            samples.size.toDouble(),
            ((1.0 - rate / expectedRateHz).coerceAtLeast(0.0) * 100.0),
        )
        if (features.size != MOVEMENT_FEATURE_NAMES.size || features.any { !it.isFinite() }) return null
        return MovementFeatures(MOVEMENT_FEATURE_NAMES, features.map(Double::toFloat).toFloatArray(), rate, samples.size)
    }

    private fun standardDeviation(values: List<Double>): Double {
        val average = values.average()
        return sqrt(values.sumOf { (it - average) * (it - average) } / values.size)
    }
}
