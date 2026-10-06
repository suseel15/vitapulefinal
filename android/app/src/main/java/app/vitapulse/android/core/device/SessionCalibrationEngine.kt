package app.vitapulse.android.core.device

import java.util.UUID
import kotlin.math.sqrt

class SessionCalibrationEngine {
    fun calibrate(
        sessionId: String,
        placement: String,
        samples: List<MovementSample>,
        timestampMs: Long = System.currentTimeMillis(),
    ): SessionCalibration {
        require(samples.size >= MINIMUM_SAMPLES) { "Calibration failed. Keep the sensor still and try again." }
        require(samples.all { it.source == SensorSource.LIVE_SENSOR }) { "Calibration accepts live sensor samples only." }
        val meanAx = samples.map { it.ax }.average()
        val meanAy = samples.map { it.ay }.average()
        val meanAz = samples.map { it.az }.average()
        val accelerationVariance = samples.sumOf {
            (it.ax - meanAx) * (it.ax - meanAx) +
                (it.ay - meanAy) * (it.ay - meanAy) +
                (it.az - meanAz) * (it.az - meanAz)
        } / samples.size
        val gyroBiasX = samples.map { it.gx }.average()
        val gyroBiasY = samples.map { it.gy }.average()
        val gyroBiasZ = samples.map { it.gz }.average()
        val gyroVariance = samples.sumOf {
            (it.gx - gyroBiasX) * (it.gx - gyroBiasX) +
                (it.gy - gyroBiasY) * (it.gy - gyroBiasY) +
                (it.gz - gyroBiasZ) * (it.gz - gyroBiasZ)
        } / samples.size
        val totalVariance = accelerationVariance + gyroVariance / 10_000.0
        val quality = when {
            totalVariance <= 0.01 -> "GOOD"
            totalVariance <= 0.05 -> "MODERATE"
            else -> "FAILED"
        }
        require(quality != "FAILED") { "Calibration failed. Keep the sensor still and try again." }
        return SessionCalibration(
            calibrationId = UUID.randomUUID().toString(),
            sessionId = sessionId,
            timestampMs = timestampMs,
            sensorPlacement = placement,
            gyroBiasX = gyroBiasX,
            gyroBiasY = gyroBiasY,
            gyroBiasZ = gyroBiasZ,
            baselineAx = meanAx,
            baselineAy = meanAy,
            baselineAz = meanAz,
            signalVariance = totalVariance,
            quality = quality,
        )
    }

    companion object {
        const val MINIMUM_SAMPLES = 30
    }
}
