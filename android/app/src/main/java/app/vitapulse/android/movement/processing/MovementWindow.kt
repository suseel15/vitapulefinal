package app.vitapulse.android.movement.processing

import app.vitapulse.android.core.device.MovementSample
import kotlin.math.roundToInt

data class WindowConfig(
    val windowDurationMs: Long = 3_000,
    val stepDurationMs: Long = 1_000,
    val minimumSamples: Int = 20,
    val requiredSamplingRateHz: Double = 8.0,
) {
    init {
        require(windowDurationMs > 0 && stepDurationMs > 0)
        require(minimumSamples >= 2 && requiredSamplingRateHz > 0)
    }
}

data class MovementWindow(
    val startTimestampMs: Long,
    val endTimestampMs: Long,
    val samples: List<MovementSample>,
    val samplingRateHz: Double,
)

class MovementWindowBuilder(
    val config: WindowConfig = WindowConfig(),
) {
    private val samples = ArrayDeque<MovementSample>()
    private var nextWindowEndMs: Long? = null

    fun add(sample: MovementSample): MovementWindow? {
        samples.addLast(sample)
        val start = samples.first().appTimestamp
        val end = sample.appTimestamp
        if (end - start < config.windowDurationMs) return null
        val nextEnd = nextWindowEndMs
        if (nextEnd != null && end < nextEnd) return null
        val windowStart = end - config.windowDurationMs
        val windowSamples = samples.filter { it.appTimestamp in windowStart..end }
        nextWindowEndMs = end + config.stepDurationMs
        while (samples.isNotEmpty() && samples.first().appTimestamp < windowStart) samples.removeFirst()
        if (windowSamples.size < config.minimumSamples) return null
        val duration = windowSamples.last().appTimestamp - windowSamples.first().appTimestamp
        if (duration <= 0) return null
        val rate = (windowSamples.size - 1) * 1000.0 / duration
        val expected = (config.windowDurationMs * config.requiredSamplingRateHz / 1000.0).roundToInt()
        if (windowSamples.size < expected || rate < config.requiredSamplingRateHz) return null
        return MovementWindow(windowSamples.first().appTimestamp, windowSamples.last().appTimestamp, windowSamples, rate)
    }

    fun reset() {
        samples.clear()
        nextWindowEndMs = null
    }
}
