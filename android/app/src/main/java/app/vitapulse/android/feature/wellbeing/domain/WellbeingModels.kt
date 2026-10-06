package app.vitapulse.android.feature.wellbeing.domain

import app.vitapulse.android.feature.wellbeing.analysis.CameraWellbeingFeatures
import app.vitapulse.android.feature.wellbeing.data.CameraWellbeingFeatureEntity
import app.vitapulse.android.feature.wellbeing.data.CameraWellbeingSessionEntity
import app.vitapulse.android.feature.wellbeing.data.SleepRecordEntity
import app.vitapulse.android.feature.wellbeing.data.WellbeingCheckInEntity
import app.vitapulse.android.feature.wellbeing.data.RecoveryRecordEntity
import app.vitapulse.android.feature.wellbeing.data.WellbeingReportEntity
import kotlin.math.abs

enum class WellbeingDataSource {
    CAMERA_OBSERVED,
    SELF_REPORTED,
    WATCH_DERIVED,
    CALCULATED,
    AI_INTERPRETED,
}

enum class CameraSessionState {
    NOT_STARTED,
    INTRO,
    PERMISSION_REQUIRED,
    PERMISSION_DENIED,
    PRECHECK,
    READY,
    COUNTDOWN,
    ACTIVE,
    PROCESSING,
    COMPLETED,
    CANCELLED,
    ERROR,
}

data class WellbeingUiState(
    val checkIns: List<WellbeingCheckInEntity> = emptyList(),
    val cameraSessions: List<CameraWellbeingSessionEntity> = emptyList(),
    val cameraFeatures: List<CameraWellbeingFeatureEntity> = emptyList(),
    val sleepRecords: List<SleepRecordEntity> = emptyList(),
    val recoveryRecords: List<RecoveryRecordEntity> = emptyList(),
    val reports: List<WellbeingReportEntity> = emptyList(),
    val latestCameraPreview: CameraWellbeingFeatures? = null,
    val busy: Boolean = false,
    val error: String? = null,
    val notice: String? = null,
    val syncState: String = "LOCAL_ONLY",
)

data class WellbeingTrend(
    val classification: String,
    val observationCount: Int,
    val direction: String?,
)

object WellbeingTrendAnalyzer {
    fun classify(values: List<Double>): WellbeingTrend {
        if (values.size < 3) return WellbeingTrend("INSUFFICIENT_DATA", values.size, null)
        val chunkSize = (values.size / 3).coerceAtLeast(1)
        val first = values.take(chunkSize).average()
        val last = values.takeLast(chunkSize).average()
        val delta = last - first
        val meanX = (values.size - 1) / 2.0
        val meanY = values.average()
        val slope = values.indices.sumOf { index -> (index - meanX) * (values[index] - meanY) } /
            values.indices.sumOf { index -> (index - meanX) * (index - meanX) }
        val intercept = meanY - slope * meanX
        val residualDeviation = kotlin.math.sqrt(
            values.indices.map { index ->
                val residual = values[index] - (intercept + slope * index)
                residual * residual
            }.average(),
        )
        val classification = when {
            residualDeviation >= 1.0 -> "VARIABLE"
            abs(delta) < 0.5 -> "STABLE"
            delta > 0 -> "IMPROVING"
            else -> "DECLINING"
        }
        return WellbeingTrend(
            classification = classification,
            observationCount = values.size,
            direction = when {
                delta > 0 -> "UP"
                delta < 0 -> "DOWN"
                else -> "UNCHANGED"
            },
        )
    }
}

data class WellbeingReportData(
    val reportType: String,
    val generatedAtMs: Long,
    val selfReport: Map<String, Int>?,
    val cameraFeatures: CameraWellbeingFeatureEntity?,
    val sleepDurationMinutes: Int?,
    val recoveryState: String?,
    val sourceProvenance: List<WellbeingDataSource>,
    val limitations: List<String>,
)

interface WellbeingDataProvider<T> {
    suspend fun latest(): T?
}

interface SelfReportProvider : WellbeingDataProvider<WellbeingCheckInEntity>
interface CameraWellbeingProvider : WellbeingDataProvider<CameraWellbeingFeatureEntity>
interface SleepProvider : WellbeingDataProvider<SleepRecordEntity>
interface RecoveryProvider : WellbeingDataProvider<RecoveryRecordEntity>
interface WatchWellbeingProvider : WellbeingDataProvider<Map<String, Any>>

interface RehabWellbeingContextProvider {
    suspend fun recentRehabLoad(): Map<String, Any>?
}

interface HealthWellbeingContextProvider {
    suspend fun authorizedHealthContext(): Map<String, Any>?
}
