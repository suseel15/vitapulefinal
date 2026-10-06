package app.vitapulse.android.movement.processing

import app.vitapulse.android.core.device.MovementSample
import app.vitapulse.android.core.device.SessionCalibration
import kotlin.math.abs
import kotlin.math.sqrt

const val SIGNAL_PROCESSING_VERSION = "movement-signal-v1"

data class FilterConfig(
    val alpha: Double = 0.35,
    val maximumAxisMagnitude: Double = 16.0,
) {
    init {
        require(alpha in 0.0..1.0)
        require(maximumAxisMagnitude > 0.0)
    }
}

data class ProcessedMovementSample(
    val raw: MovementSample,
    val accelerationMagnitude: Double,
    val dynamicAccelerationMagnitude: Double,
    val angularVelocityMagnitude: Double,
    val processingVersion: String = SIGNAL_PROCESSING_VERSION,
)

class SignalProcessor(
    private val config: FilterConfig = FilterConfig(),
) {
    private var filteredAcceleration: Double? = null
    private var filteredGyroscope: Double? = null

    fun process(sample: MovementSample, calibration: SessionCalibration?): ProcessedMovementSample? {
        val axes = listOf(sample.ax, sample.ay, sample.az, sample.gx, sample.gy, sample.gz)
        if (axes.any { !it.isFinite() || abs(it) > config.maximumAxisMagnitude }) return null
        val acceleration = sample.accelerationMagnitude
        val gyroBiasCorrected = sqrt(
            (sample.gx - (calibration?.gyroBiasX ?: 0.0)).let { it * it } +
                (sample.gy - (calibration?.gyroBiasY ?: 0.0)).let { it * it } +
                (sample.gz - (calibration?.gyroBiasZ ?: 0.0)).let { it * it },
        )
        val smoothedAcceleration = smooth(filteredAcceleration, acceleration).also { filteredAcceleration = it }
        val smoothedGyro = smooth(filteredGyroscope, gyroBiasCorrected).also { filteredGyroscope = it }
        val calibratedBaseline = calibration?.baselineMagnitude ?: acceleration
        return ProcessedMovementSample(
            raw = sample,
            accelerationMagnitude = smoothedAcceleration,
            dynamicAccelerationMagnitude = abs(smoothedAcceleration - calibratedBaseline),
            angularVelocityMagnitude = smoothedGyro,
        )
    }

    fun reset() {
        filteredAcceleration = null
        filteredGyroscope = null
    }

    private fun smooth(previous: Double?, current: Double): Double =
        previous?.let { config.alpha * current + (1.0 - config.alpha) * it } ?: current
}
