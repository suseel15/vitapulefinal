package app.vitapulse.android.core.healthconnect

import com.google.gson.JsonParser
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

data class HealthContextMetric(
    val label: String,
    val value: String,
    val source: String,
    val sourceApplication: String,
    val recordAtMs: Long,
    val syncedAtMs: Long,
)

data class RecoveryDataSnapshot(
    val sleep: HealthContextMetric? = null,
    val activity: HealthContextMetric? = null,
    val heartRate: HealthContextMetric? = null,
)

interface RecoveryDataProvider {
    fun observeRecoveryContext(): Flow<RecoveryDataSnapshot>
}

class RoomRecoveryDataProvider(private val dao: HealthDataDao) : RecoveryDataProvider {
    override fun observeRecoveryContext(): Flow<RecoveryDataSnapshot> = combine(
        dao.observeRecordsByType(HealthDataType.SLEEP.name),
        dao.observeRecordsByType(HealthDataType.STEPS.name),
        dao.observeRecordsByType(HealthDataType.HEART_RATE.name),
    ) { sleep, steps, heartRate ->
        summarizeHealthContext(sleep, steps, heartRate)
    }
}

fun summarizeHealthContext(
    sleepRecords: List<HealthDataEntity>,
    stepRecords: List<HealthDataEntity>,
    heartRateRecords: List<HealthDataEntity>,
    now: Instant = Instant.now(),
    zoneId: ZoneId = ZoneId.systemDefault(),
): RecoveryDataSnapshot {
    val nowMs = now.toEpochMilli()
    val latestSleep = sleepRecords
        .filter { it.recordEndMs <= nowMs && nowMs - it.recordEndMs <= SLEEP_FRESHNESS_MS }
        .maxByOrNull(HealthDataEntity::recordEndMs)
        ?.let { record ->
            val minutes = JsonParser.parseString(record.payloadJson).asJsonObject.get("durationMinutes").asInt
            if (minutes !in 1..1440) null else record.metric("Sleep", "${minutes / 60}h ${minutes % 60}m")
        }
    val todayStart = LocalDate.ofInstant(now, zoneId).atStartOfDay(zoneId).toInstant().toEpochMilli()
    val currentDaySteps = stepRecords.filter {
        it.recordStartMs >= todayStart && it.recordEndMs <= nowMs && it.recordEndMs >= it.recordStartMs
    }
    val selectedStepSource = currentDaySteps.maxByOrNull(HealthDataEntity::recordEndMs)?.sourceApplication
    val todayStepRecords = currentDaySteps.filter { it.sourceApplication == selectedStepSource }
    val stepsMetric = if (todayStepRecords.isEmpty()) {
        null
    } else {
        val total = todayStepRecords.sumOf {
            JsonParser.parseString(it.payloadJson).asJsonObject.get("count").asLong
        }
        val latest = todayStepRecords.maxBy(HealthDataEntity::recordEndMs)
        latest.metric("Activity", "$total steps today")
    }
    val latestHeartRate = heartRateRecords
        .filter { it.recordEndMs <= nowMs && nowMs - it.recordEndMs <= HEART_RATE_FRESHNESS_MS }
        .maxByOrNull(HealthDataEntity::recordEndMs)
        ?.let { record ->
            val samples = JsonParser.parseString(record.payloadJson).asJsonObject.getAsJsonArray("samples")
            val values = samples.map { it.asJsonObject.get("beatsPerMinute").asLong }
            if (values.isEmpty() || values.any { it !in 25L..250L }) {
                null
            } else {
                record.metric("Heart rate", "${values.average().toInt()} bpm average")
            }
        }
    return RecoveryDataSnapshot(latestSleep, stepsMetric, latestHeartRate)
}

private fun HealthDataEntity.metric(label: String, value: String) = HealthContextMetric(
    label = label,
    value = value,
    source = source,
    sourceApplication = sourceApplication,
    recordAtMs = recordEndMs,
    syncedAtMs = syncedAtMs,
)

private const val SLEEP_FRESHNESS_MS = 48L * 60 * 60 * 1000
private const val HEART_RATE_FRESHNESS_MS = 24L * 60 * 60 * 1000
