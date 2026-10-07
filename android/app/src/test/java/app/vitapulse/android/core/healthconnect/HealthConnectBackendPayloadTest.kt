package app.vitapulse.android.core.healthconnect

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class HealthConnectBackendPayloadTest {
    @Test
    fun heartRateUploadContainsSummaryAndNeverRawSamples() {
        val record = entity(
            type = HealthDataType.HEART_RATE,
            payload = """{"samples":[{"time":"2026-01-01T10:00:00Z","beatsPerMinute":70},{"time":"2026-01-01T10:01:00Z","beatsPerMinute":80}]}""",
        )

        val upload = buildHealthConnectUploadRequest(listOf(record))
        val values = (upload["records"] as List<*>).single() as Map<*, *>
        val summary = values["value"] as Map<*, *>

        assertEquals(75.0, summary["average_bpm"])
        assertEquals(2, summary["sample_count"])
        assertFalse(summary.containsKey("samples"))
    }

    @Test
    fun oxygenSaturationUploadUsesPercentUnits() {
        val upload = buildHealthConnectUploadRequest(
            listOf(entity(HealthDataType.OXYGEN_SATURATION, """{"percentage":0.97}""")),
        )
        val values = (upload["records"] as List<*>).single() as Map<*, *>
        val summary = values["value"] as Map<*, *>

        assertEquals(97.0, summary["percentage"])
    }

    @Test
    fun uploadRangeIsBoundedAndOnlyHealthConnectRecordsAreAccepted() {
        val healthRecord = entity(HealthDataType.STEPS, """{"count":1250}""")
        val otherSource = healthRecord.copy(source = "MANUAL")

        assertTrue(runCatching { buildHealthConnectUploadRequest(listOf(healthRecord)) }.isSuccess)
        assertTrue(runCatching { buildHealthConnectUploadRequest(listOf(otherSource)) }.isFailure)
        assertTrue(
            runCatching {
                buildHealthConnectUploadRequest(
                    listOf(
                        healthRecord.copy(recordStartMs = 0, recordEndMs = 1),
                        healthRecord.copy(
                            deduplicationKey = "second",
                            sourceRecordId = "second",
                            recordStartMs = 31L * 24 * 60 * 60 * 1000,
                            recordEndMs = 31L * 24 * 60 * 60 * 1000 + 1,
                        ),
                    ),
                )
            }.isFailure,
        )
    }

    @Test
    fun recordValidationRejectsEmptyHeartRateAndFutureIntervals() {
        val now = Instant.now()
        val emptyHeartRate = HeartRateRecord(
            sourceId = "record-1",
            sourceApplication = "com.example.health",
            startTime = now,
            endTime = now,
            lastModified = now,
            samples = emptyList(),
        )
        val futureSteps = StepsRecord(
            sourceId = "record-2",
            sourceApplication = "com.example.health",
            startTime = now.plusSeconds(600),
            endTime = now.plusSeconds(900),
            lastModified = now,
            count = 10,
        )

        assertFalse(emptyHeartRate.isValid())
        assertFalse(futureSteps.isValid())
    }

    @Test
    fun deduplicationKeyIsStableAndScopedToSourceTypeAndId() {
        val now = Instant.now()
        val first = StepsRecord("HEALTH_CONNECT", "same-id", "com.example.health", now, now, now, 10)
        val same = first.copy()
        val sameIdDifferentOrigin = first.copy(sourceApplication = "com.other.health")
        val otherSource = first.copy(source = "LOCAL")
        val otherType = HeartRateRecord(
            source = "HEALTH_CONNECT",
            sourceId = "same-id",
            sourceApplication = "com.example.health",
            startTime = now,
            endTime = now,
            lastModified = now,
            samples = listOf(HeartRateSample(now, 70)),
        )

        assertEquals(first.deduplicationKey(), same.deduplicationKey())
        assertEquals(first.deduplicationKey(), sameIdDifferentOrigin.deduplicationKey())
        assertNotEquals(first.deduplicationKey(), otherSource.deduplicationKey())
        assertNotEquals(first.deduplicationKey(), otherType.deduplicationKey())
    }

    private fun entity(
        type: HealthDataType,
        payload: String,
    ): HealthDataEntity {
        val start = Instant.parse("2026-01-01T10:00:00Z").toEpochMilli()
        return HealthDataEntity(
            deduplicationKey = "$type-record",
            source = "HEALTH_CONNECT",
            sourceRecordId = "record-123",
            sourceApplication = "com.example.health",
            dataType = type.name,
            recordStartMs = start,
            recordEndMs = start + 60_000,
            lastModifiedMs = start,
            syncedAtMs = start,
            payloadJson = payload,
            backendUploadedAtMs = null,
        )
    }
}
