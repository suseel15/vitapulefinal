package app.vitapulse.android.core.device

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class SessionCalibrationEngineTest {
    private val engine = SessionCalibrationEngine()

    @Test
    fun calibratesStableLiveSensorSamplesForTheSelectedPlacement() {
        val calibration = engine.calibrate("session-1", "THIGH", List(30) { sample(it * 100L) }, timestampMs = 1_000L)

        assertEquals("GOOD", calibration.quality)
        assertEquals("THIGH", calibration.sensorPlacement)
        assertEquals(30, List(30) { sample(it * 100L) }.size)
        assertEquals(0.0, calibration.gyroBiasZ, 0.0001)
        assertEquals(1.0, calibration.baselineMagnitude, 0.0001)
    }

    @Test
    fun rejectsTooFewSamplesAndUnstableMovement() {
        assertThrows(IllegalArgumentException::class.java) {
            engine.calibrate("session-1", "THIGH", List(29) { sample(it.toLong()) })
        }
        val unstable = List(30) { index ->
            sample(index.toLong(), ax = if (index % 2 == 0) 1.0 else -1.0)
        }
        assertThrows(IllegalArgumentException::class.java) {
            engine.calibrate("session-1", "THIGH", unstable)
        }
    }

    private fun sample(timestamp: Long, ax: Double = 0.0) = MovementSample(
        appTimestamp = timestamp,
        ax = ax,
        ay = 0.0,
        az = 1.0,
        gx = 0.0,
        gy = 0.0,
        gz = 0.0,
        source = SensorSource.LIVE_SENSOR,
        deviceId = "ESP32-001",
        sensorType = "MPU6050",
        transport = "HTTP",
    )
}
