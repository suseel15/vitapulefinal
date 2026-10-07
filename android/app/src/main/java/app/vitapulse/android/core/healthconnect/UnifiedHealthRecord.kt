package app.vitapulse.android.core.healthconnect

import java.time.Instant

enum class HealthDataType(val historyDays: Long, val label: String) {
    SLEEP(30, "Sleep"),
    HEART_RATE(7, "Heart rate"),
    STEPS(30, "Steps"),
    EXERCISE(30, "Exercise"),
    OXYGEN_SATURATION(7, "Oxygen saturation"),
}

enum class HealthConnectAvailability {
    AVAILABLE,
    UNAVAILABLE,
    NEEDS_UPDATE,
}

enum class HealthSyncStatus {
    NOT_STARTED,
    CHECKING,
    PERMISSION_REQUIRED,
    SYNCING,
    SYNCED,
    PARTIAL,
    NO_DATA,
    FAILED,
    CANCELLED,
}

sealed interface UnifiedHealthRecord {
    val source: String
    val sourceId: String
    val sourceApplication: String
    val startTime: Instant
    val endTime: Instant
    val lastModified: Instant
    val dataType: HealthDataType

    fun payloadJson(gson: com.google.gson.Gson): String = gson.toJson(this)
}

data class SleepStageData(
    val stage: Int,
    val startTime: Instant,
    val endTime: Instant,
)

data class SleepRecord(
    override val source: String = "HEALTH_CONNECT",
    override val sourceId: String,
    override val sourceApplication: String,
    override val startTime: Instant,
    override val endTime: Instant,
    override val lastModified: Instant,
    val durationMinutes: Long,
    val stages: List<SleepStageData>,
    override val dataType: HealthDataType = HealthDataType.SLEEP,
) : UnifiedHealthRecord

data class HeartRateSample(
    val time: Instant,
    val beatsPerMinute: Long,
)

data class HeartRateRecord(
    override val source: String = "HEALTH_CONNECT",
    override val sourceId: String,
    override val sourceApplication: String,
    override val startTime: Instant,
    override val endTime: Instant,
    override val lastModified: Instant,
    val samples: List<HeartRateSample>,
    override val dataType: HealthDataType = HealthDataType.HEART_RATE,
) : UnifiedHealthRecord

data class StepsRecord(
    override val source: String = "HEALTH_CONNECT",
    override val sourceId: String,
    override val sourceApplication: String,
    override val startTime: Instant,
    override val endTime: Instant,
    override val lastModified: Instant,
    val count: Long,
    override val dataType: HealthDataType = HealthDataType.STEPS,
) : UnifiedHealthRecord

data class ExerciseRecord(
    override val source: String = "HEALTH_CONNECT",
    override val sourceId: String,
    override val sourceApplication: String,
    override val startTime: Instant,
    override val endTime: Instant,
    override val lastModified: Instant,
    val exerciseType: Int,
    val title: String?,
    override val dataType: HealthDataType = HealthDataType.EXERCISE,
) : UnifiedHealthRecord

data class OxygenSaturationRecord(
    override val source: String = "HEALTH_CONNECT",
    override val sourceId: String,
    override val sourceApplication: String,
    override val startTime: Instant,
    override val endTime: Instant,
    override val lastModified: Instant,
    val percentage: Double,
    override val dataType: HealthDataType = HealthDataType.OXYGEN_SATURATION,
) : UnifiedHealthRecord

data class HealthDataSyncResult(
    val status: HealthSyncStatus,
    val recordsFound: Int = 0,
    val recordsImported: Int = 0,
    val recordsSkipped: Int = 0,
    val recordsPendingUpload: Int = 0,
    val errors: Map<HealthDataType, String> = emptyMap(),
    val completedAt: Instant = Instant.now(),
)

fun UnifiedHealthRecord.isValid(): Boolean {
    val latestAllowed = Instant.now().plusSeconds(300)
    if (
        endTime < startTime ||
        sourceId.isBlank() ||
        sourceApplication.isBlank() ||
        startTime > latestAllowed ||
        endTime > latestAllowed
    ) return false
    return when (this) {
        is SleepRecord -> durationMinutes in 1..1440 && endTime > startTime && stages.all {
            it.endTime > it.startTime && it.startTime >= startTime && it.endTime <= endTime
        }
        is HeartRateRecord -> samples.isNotEmpty() && samples.all {
            it.beatsPerMinute in 25..250 && it.time >= startTime && it.time <= endTime
        }
        is StepsRecord -> count in 0..10_000_000 && endTime > startTime
        is ExerciseRecord -> exerciseType in 0..10_000 && endTime > startTime &&
            java.time.Duration.between(startTime, endTime).toMinutes() in 1..1440
        is OxygenSaturationRecord -> percentage.isFinite() && percentage in 0.0..1.0
    }
}

fun UnifiedHealthRecord.deduplicationKey(): String {
    val identity = if (sourceId.isNotBlank()) {
        "$source|$sourceId|$dataType"
    } else {
        "$source|$dataType|$startTime|$endTime"
    }
    val digest = java.security.MessageDigest.getInstance("SHA-256")
        .digest(identity.toByteArray(Charsets.UTF_8))
    return digest.joinToString("") { byte -> "%02x".format(byte) }
}
