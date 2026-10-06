package app.vitapulse.android.movement.data

import app.vitapulse.android.core.device.MovementSampleEntity
import app.vitapulse.android.core.device.MovementSessionEntity
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.util.zip.ZipInputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class MovementDatasetExporterTest {
    @Test
    fun writesPseudonymousLiveSamplesWithExplicitManualLabel() {
        val output = ByteArrayOutputStream()
        val pseudonym = MovementDatasetExporter.pseudonym("athlete-id", "installation-salt")
        val count = MovementDatasetExporter.writeArchive(
            output,
            session(source = "LIVE_SENSOR"),
            (0..30).map { index ->
                MovementSampleEntity("session-id", index * 100L, 0.1, 0.2, 1.0, 0.01, 0.02, 0.03)
            }.asReversed(),
            pseudonym,
        )

        assertEquals(31, count)
        val entries = mutableMapOf<String, String>()
        ZipInputStream(ByteArrayInputStream(output.toByteArray())).use { zip ->
            var entry = zip.nextEntry
            while (entry != null) {
                entries[entry.name] = zip.readBytes().toString(Charsets.UTF_8)
                entry = zip.nextEntry
            }
        }
        assertEquals(setOf("metadata.csv", "samples.csv", "labels.csv"), entries.keys)
        assertTrue(entries.getValue("metadata.csv").contains(pseudonym))
        assertFalse(entries.getValue("metadata.csv").contains("athlete-id"))
        assertTrue(entries.getValue("labels.csv").contains("SQUAT,MANUAL"))
        assertEquals(32, entries.getValue("samples.csv").lineSequence().count())
    }

    @Test
    fun refusesNonLiveSessions() {
        assertThrows(IllegalArgumentException::class.java) {
            MovementDatasetExporter.writeArchive(
                ByteArrayOutputStream(),
                session(source = "SIMULATION"),
                (0..30).map { index ->
                    MovementSampleEntity("session-id", index * 100L, 0.1, 0.2, 1.0, 0.01, 0.02, 0.03)
                },
                "pseudonym_0001",
            )
        }
    }

    private fun session(source: String) = MovementSessionEntity(
        id = "session-id",
        exerciseName = "Single-Leg Squat",
        exerciseId = "exercise-id",
        deviceIdentifier = "ESP32-001",
        registeredDeviceId = null,
        sensorType = "MPU6050",
        transport = "HTTP",
        source = source,
        sensorPlacement = "THIGH",
        targetRepetitions = 10,
        backendSessionId = null,
        status = "COMPLETED",
        startedAtMs = 0,
        endedAtMs = 3000,
        sampleCount = 31,
        successfulRequests = 31,
        failedRequests = 0,
        invalidSamples = 0,
        averageLatencyMs = 12.0,
        measuredRateHz = 10.0,
        movementQuality = "GOOD",
        stability = "STABLE",
        smoothness = "SMOOTH",
        fatigueSignal = "INSUFFICIENT_DATA",
        repetitions = 10,
        syncState = "SYNCED",
        ownerId = "athlete-id",
        consistency = null,
        sensorQuality = "GOOD",
        recognition = null,
        recognizedExercise = null,
        modelName = null,
        modelVersion = null,
        baselineStatus = null,
        anomalyCount = 0,
    )
}
