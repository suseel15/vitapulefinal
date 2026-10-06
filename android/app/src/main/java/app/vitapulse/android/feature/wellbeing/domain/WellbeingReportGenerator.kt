package app.vitapulse.android.feature.wellbeing.domain

import app.vitapulse.android.feature.wellbeing.data.CameraWellbeingFeatureEntity
import app.vitapulse.android.feature.wellbeing.data.CameraWellbeingSessionEntity
import app.vitapulse.android.feature.wellbeing.data.RecoveryRecordEntity
import app.vitapulse.android.feature.wellbeing.data.SleepRecordEntity
import app.vitapulse.android.feature.wellbeing.data.WellbeingCheckInEntity

class WellbeingReportGenerator {
    fun generate(
        reportType: String,
        checkIn: WellbeingCheckInEntity?,
        cameraSession: CameraWellbeingSessionEntity?,
        cameraFeatures: CameraWellbeingFeatureEntity?,
        sleep: SleepRecordEntity?,
        recovery: RecoveryRecordEntity?,
    ): WellbeingReportData {
        val sources = buildList {
            if (checkIn != null) add(WellbeingDataSource.SELF_REPORTED)
            if (cameraSession != null && cameraFeatures != null) add(WellbeingDataSource.CAMERA_OBSERVED)
            if (sleep != null) {
                add(
                    if (sleep.source == "WATCH_DERIVED" || sleep.source == "HEALTH_CONNECT") {
                        WellbeingDataSource.WATCH_DERIVED
                    } else {
                        WellbeingDataSource.SELF_REPORTED
                    },
                )
            }
            if (recovery != null) add(WellbeingDataSource.CALCULATED)
        }
        return WellbeingReportData(
            reportType = reportType,
            generatedAtMs = System.currentTimeMillis(),
            selfReport = checkIn?.let {
                mapOf(
                    "energy" to it.energy,
                    "stress" to it.stress,
                    "fatigue" to it.fatigue,
                    "soreness" to it.soreness,
                    "recoveryFeeling" to it.recoveryFeeling,
                )
            },
            cameraFeatures = cameraFeatures,
            sleepDurationMinutes = sleep?.durationMinutes,
            recoveryState = recovery?.recoveryState,
            sourceProvenance = sources,
            limitations = listOf(
                "This report is not a medical or mental-health diagnosis.",
                "Camera features are observations only and are not used to infer identity or psychological state.",
                "Missing sources are not estimated or filled with sample values.",
            ),
        )
    }
}
