package app.vitapulse.android.core.healthconnect

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.Instant
import java.time.ZoneOffset

class RecoveryDataProviderTest {
    private val now = Instant.parse("2026-10-06T12:00:00Z")
    private val todayStart = Instant.parse("2026-10-06T00:00:00Z").toEpochMilli()

    @Test
    fun summarizesFreshRecordsWithTheirOriginAndDistinctRecordAndSyncTimes() {
        val sleep = record(
            type = HealthDataType.SLEEP,
            startMs = now.minusSeconds(8 * 60 * 60).toEpochMilli(),
            endMs = now.minusSeconds(60 * 60).toEpochMilli(),
            syncedAtMs = now.toEpochMilli(),
            payload = """{"durationMinutes":480,"stages":[]}""",
        )
        val steps = listOf(
            record(HealthDataType.STEPS, todayStart + 1_000, todayStart + 2_000, "app.first", """{"count":900}"""),
            record(HealthDataType.STEPS, todayStart + 3_000, todayStart + 4_000, "app.selected", """{"count":1200}"""),
            record(HealthDataType.STEPS, todayStart + 5_000, todayStart + 6_000, "app.selected", """{"count":800}"""),
        )
        val heartRate = record(
            HealthDataType.HEART_RATE,
            now.minusSeconds(300).toEpochMilli(),
            now.minusSeconds(120).toEpochMilli(),
            payload = """{"samples":[{"beatsPerMinute":60},{"beatsPerMinute":80}]}""",
        )

        val result = summarizeHealthContext(
            sleepRecords = listOf(sleep),
            stepRecords = steps,
            heartRateRecords = listOf(heartRate),
            now = now,
            zoneId = ZoneOffset.UTC,
        )

        assertEquals("8h 0m", result.sleep?.value)
        assertEquals(sleep.recordEndMs, result.sleep?.recordAtMs)
        assertEquals(sleep.syncedAtMs, result.sleep?.syncedAtMs)
        assertEquals("2000 steps today", result.activity?.value)
        assertEquals("app.selected", result.activity?.sourceApplication)
        assertEquals("70 bpm average", result.heartRate?.value)
    }

    @Test
    fun excludesStaleAndFutureRecords() {
        val staleSleep = record(
            HealthDataType.SLEEP,
            now.minusSeconds(72 * 60 * 60).toEpochMilli(),
            now.minusSeconds(49 * 60 * 60).toEpochMilli(),
            payload = """{"durationMinutes":420,"stages":[]}""",
        )
        val futureHeartRate = record(
            HealthDataType.HEART_RATE,
            now.plusSeconds(60).toEpochMilli(),
            now.plusSeconds(120).toEpochMilli(),
            payload = """{"samples":[{"beatsPerMinute":72}]}""",
        )
        val yesterdaySteps = record(
            HealthDataType.STEPS,
            todayStart - 2_000,
            todayStart - 1_000,
            payload = """{"count":4000}""",
        )

        val result = summarizeHealthContext(
            sleepRecords = listOf(staleSleep),
            stepRecords = listOf(yesterdaySteps),
            heartRateRecords = listOf(futureHeartRate),
            now = now,
            zoneId = ZoneOffset.UTC,
        )

        assertNull(result.sleep)
        assertNull(result.activity)
        assertNull(result.heartRate)
    }

    private fun record(
        type: HealthDataType,
        startMs: Long,
        endMs: Long,
        sourceApplication: String = "com.example.health",
        payload: String,
        syncedAtMs: Long = now.toEpochMilli(),
    ) = HealthDataEntity(
        deduplicationKey = "$type-$startMs-$sourceApplication",
        source = "HEALTH_CONNECT",
        sourceRecordId = "$type-$startMs",
        sourceApplication = sourceApplication,
        dataType = type.name,
        recordStartMs = startMs,
        recordEndMs = endMs,
        lastModifiedMs = endMs,
        syncedAtMs = syncedAtMs,
        payloadJson = payload,
        backendUploadedAtMs = null,
    )
}
