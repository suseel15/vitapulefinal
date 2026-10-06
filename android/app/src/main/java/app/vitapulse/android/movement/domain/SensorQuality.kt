package app.vitapulse.android.movement.domain

import app.vitapulse.android.core.device.MovementSample
import kotlin.math.abs
import kotlin.math.sqrt

enum class SensorQualityStatus { EXCELLENT, GOOD, DEGRADED, POOR, INSUFFICIENT }

data class SensorQualityMetrics(
    val status: SensorQualityStatus,
    val sampleCount: Int,
    val samplingRateHz: Double?,
    val missingSamplesPercentage: Double?,
    val variance: Double?,
    val clippingCount: Int,
    val staleSamples: Int,
)

class SensorQualityMonitor(
    private val requiredRateHz: Double = 8.0,
    private val expectedRateHz: Double = 10.0,
) {
    fun assess(samples: List<MovementSample>, invalidSamples: Int = 0, failedRequests: Int = 0): SensorQualityMetrics {
        require(invalidSamples >= 0 && failedRequests >= 0)
        if (samples.size < 2) return SensorQualityMetrics(SensorQualityStatus.INSUFFICIENT, samples.size, null, null, null, 0, 0)
        val ordered = samples.sortedBy { it.appTimestamp }
        val deltas = ordered.zipWithNext().map { (left, right) -> right.appTimestamp - left.appTimestamp }
        val duration = ordered.last().appTimestamp - ordered.first().appTimestamp
        if (duration <= 0 || deltas.any { it <= 0 }) {
            return SensorQualityMetrics(SensorQualityStatus.INSUFFICIENT, samples.size, null, null, null, 0, 0)
        }
        val rate = (samples.size - 1) * 1000.0 / duration
        val estimated = (duration * expectedRateHz / 1000.0).toInt() + 1
        val missing = ((estimated - samples.size).coerceAtLeast(0) * 100.0 / estimated)
        val magnitudes = ordered.map { it.accelerationMagnitude }
        val mean = magnitudes.average()
        val variance = magnitudes.sumOf { (it - mean) * (it - mean) } / magnitudes.size
        val stale = deltas.count { it > 1_500 }
        val clipped = ordered.count { sample ->
            listOf(sample.ax, sample.ay, sample.az, sample.gx, sample.gy, sample.gz).any { abs(it) >= 16 }
        }
        val badRatio = (invalidSamples + failedRequests).toDouble() / (samples.size + invalidSamples).coerceAtLeast(1)
        val status = when {
            rate < requiredRateHz || badRatio >= 0.25 || stale >= 2 -> SensorQualityStatus.INSUFFICIENT
            badRatio >= 0.10 || stale > 0 || clipped > 0 -> SensorQualityStatus.POOR
            missing >= 10 -> SensorQualityStatus.DEGRADED
            missing >= 3 -> SensorQualityStatus.GOOD
            else -> SensorQualityStatus.EXCELLENT
        }
        return SensorQualityMetrics(status, samples.size, rate, missing, variance, clipped, stale)
    }
}
