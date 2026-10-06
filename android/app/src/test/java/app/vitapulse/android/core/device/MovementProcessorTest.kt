package app.vitapulse.android.core.device

import org.junit.Assert.assertEquals
import org.junit.Test

class MovementProcessorTest {
    @Test
    fun signalsInsufficientDataUntilEnoughLiveReadingsAreCollected() {
        val processor = MovementProcessor()
        val result = processor.add(sample(0L, 1.0), null)

        assertEquals("INSUFFICIENT_DATA", result.movementQuality)
        assertEquals(0, result.repetitionCount)
    }

    @Test
    fun resetClearsTheSessionWindowAndRepetitionCount() {
        val processor = MovementProcessor()
        repeat(12) { processor.add(sample(it * 100L, 1.0), null) }

        processor.reset()

        assertEquals("INSUFFICIENT_DATA", processor.summarize().movementQuality)
        assertEquals(0, processor.repetitionCount)
    }

    private fun sample(timestamp: Long, az: Double) = MovementSample(
        appTimestamp = timestamp,
        ax = 0.0,
        ay = 0.0,
        az = az,
        gx = 0.0,
        gy = 0.0,
        gz = 0.0,
        source = SensorSource.LIVE_SENSOR,
        deviceId = "ESP32-001",
        sensorType = "MPU6050",
        transport = "HTTP",
    )
}
