package app.vitapulse.android.feature.wellbeing

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import app.vitapulse.android.VitaPulseApplication
import app.vitapulse.android.feature.wellbeing.analysis.CameraWellbeingFeatureExtractor
import app.vitapulse.android.feature.wellbeing.analysis.FrameObservation
import app.vitapulse.android.feature.wellbeing.data.CameraWellbeingFeatureEntity
import app.vitapulse.android.feature.wellbeing.data.CameraWellbeingSessionEntity
import app.vitapulse.android.feature.wellbeing.data.RecoveryRecordEntity
import app.vitapulse.android.feature.wellbeing.data.SleepRecordEntity
import app.vitapulse.android.feature.wellbeing.data.WellbeingCheckInEntity
import app.vitapulse.android.feature.wellbeing.data.WellbeingReportEntity
import app.vitapulse.android.feature.wellbeing.domain.WellbeingReportGenerator
import app.vitapulse.android.feature.wellbeing.domain.WellbeingTrendAnalyzer
import app.vitapulse.android.feature.wellbeing.domain.WellbeingUiState
import com.google.gson.Gson
import java.time.Instant
import java.time.LocalDate
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class WellbeingViewModel(private val app: VitaPulseApplication) : ViewModel() {
    private val dao = app.wellbeingDatabase.wellbeingDao()
    private val gson = Gson()
    private val _state = MutableStateFlow(WellbeingUiState())
    val state: StateFlow<WellbeingUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            try {
                val ownerId = app.backendClient.currentAthleteId()
                val current = withContext(Dispatchers.IO) {
                    val cameraSessions = dao.cameraSessions(ownerId)
                    WellbeingUiState(
                        checkIns = dao.checkIns(ownerId),
                        cameraSessions = cameraSessions,
                        cameraFeatures = cameraSessions.mapNotNull { dao.cameraFeatures(it.id, ownerId) },
                        sleepRecords = dao.sleepRecords(ownerId),
                        recoveryRecords = dao.recoveryRecords(ownerId),
                        reports = dao.reports(ownerId),
                    )
                }
                _state.value = current.copy(
                    syncState = syncStateLabel(current),
                )
            } catch (error: Exception) {
                _state.value = _state.value.copy(error = error.message ?: "Wellbeing history could not be loaded.")
            }
        }
    }

    fun saveCheckIn(
        energy: Int,
        stress: Int,
        fatigue: Int,
        soreness: Int,
        recoveryFeeling: Int,
        note: String,
    ) {
        if (listOf(energy, stress, fatigue, soreness, recoveryFeeling).any { it !in 1..5 }) {
            _state.value = _state.value.copy(error = "Choose a response for every wellbeing scale.")
            return
        }
        viewModelScope.launch {
            val now = System.currentTimeMillis()
            val record = WellbeingCheckInEntity(
                id = UUID.randomUUID().toString(),
                ownerId = app.backendClient.currentAthleteId(),
                energy = energy,
                stress = stress,
                fatigue = fatigue,
                soreness = soreness,
                recoveryFeeling = recoveryFeeling,
                moodSelfReport = null,
                note = note.trim().takeIf { it.isNotEmpty() },
                createdAtMs = now,
                updatedAtMs = now,
                syncState = pendingOrLocal(),
            )
            withContext(Dispatchers.IO) { dao.saveCheckIn(record) }
            if (record.syncState == "SYNC_PENDING") {
                syncSafely {
                    app.backendClient.syncWellbeingCheckIn(checkInPayload(record))
                    dao.updateCheckInSyncState(record.id, "SYNCED")
                }
            }
            _state.value = _state.value.copy(notice = "Check-in saved. Your responses remain self-reported.")
            refresh()
        }
    }

    fun saveSleep(
        startAtMs: Long,
        endAtMs: Long,
        quality: Int?,
        interruptions: Int?,
        note: String,
    ) {
        val duration = ((endAtMs - startAtMs) / 60_000L).toInt()
        if (duration !in 1..1440) {
            _state.value = _state.value.copy(error = "Enter bedtime and wake time within a 24-hour interval.")
            return
        }
        if (quality != null && quality !in 1..5) {
            _state.value = _state.value.copy(error = "Sleep quality must be between 1 and 5.")
            return
        }
        viewModelScope.launch {
            val record = SleepRecordEntity(
                id = UUID.randomUUID().toString(),
                ownerId = app.backendClient.currentAthleteId(),
                startAtMs = startAtMs,
                endAtMs = endAtMs,
                durationMinutes = duration,
                qualityRating = quality,
                interruptions = interruptions,
                notes = note.trim().takeIf { it.isNotEmpty() },
                source = "SELF_REPORTED",
                sourceId = null,
                createdAtMs = System.currentTimeMillis(),
                syncState = pendingOrLocal(),
            )
            withContext(Dispatchers.IO) { dao.saveSleep(record) }
            if (record.syncState == "SYNC_PENDING") {
                syncSafely {
                    app.backendClient.syncWellbeingSleep(sleepPayload(record))
                    dao.updateSleepSyncState(record.id, "SYNCED")
                }
            }
            _state.value = _state.value.copy(notice = "Sleep entry saved · Source: SELF_REPORTED.")
            refresh()
        }
    }

    fun saveCameraAssessment(
        startedAtMs: Long,
        observations: List<FrameObservation>,
        durationSeconds: Int,
        storeHistory: Boolean,
        onSaved: () -> Unit,
    ) {
        viewModelScope.launch {
            if (observations.isEmpty()) {
                _state.value = _state.value.copy(error = "No camera observations were captured. Try again when your face is in view.")
                return@launch
            }
            val features = CameraWellbeingFeatureExtractor.extract(observations, durationSeconds)
            val sessionId = UUID.randomUUID().toString()
            val now = System.currentTimeMillis()
            val accepted = durationSeconds == 30 &&
                features.captureQuality in setOf("GOOD", "FAIR") &&
                features.validFrameRatio >= 0.5
            val session = CameraWellbeingSessionEntity(
                id = sessionId,
                ownerId = app.backendClient.currentAthleteId(),
                startedAtMs = startedAtMs,
                completedAtMs = now,
                durationSeconds = durationSeconds,
                status = if (accepted) "COMPLETED" else "INCOMPLETE",
                captureQuality = features.captureQuality,
                validFrameRatio = features.validFrameRatio,
                facePresenceRatio = features.facePresenceRatio,
                multipleFaceFrames = features.multipleFaceFrames,
                syncState = pendingOrLocal(),
            )
            val feature = CameraWellbeingFeatureEntity(
                id = UUID.randomUUID().toString(),
                sessionId = sessionId,
                ownerId = session.ownerId,
                facePresenceRatio = features.facePresenceRatio,
                facePositionStability = features.facePositionStability,
                headMovementMagnitude = features.headMovementMagnitude,
                headMovementVariability = features.headMovementVariability,
                headOrientationRange = features.headOrientationRange,
                eyeObservationRatio = features.eyeObservationRatio,
                smileObservationRatio = features.smileObservationRatio,
                facialFeatureMovement = null,
                faceDetectedFrames = features.faceDetectedFrames,
                validFrames = features.validFrames,
                invalidFrames = features.invalidFrames,
                poorLightingFrames = features.poorLightingFrames,
                faceOutOfFrameFrames = features.faceOutOfFrameFrames,
                captureQuality = features.captureQuality,
                featureSchemaVersion = CameraWellbeingFeatureExtractor.FEATURE_SCHEMA_VERSION,
                createdAtMs = now,
            )
            if (storeHistory) withContext(Dispatchers.IO) {
                dao.saveCameraSession(session)
                dao.saveCameraFeatures(feature)
            }
            val synced = if (storeHistory && session.syncState == "SYNC_PENDING") {
                syncSafely {
                    app.backendClient.syncCameraWellbeingSession(cameraSessionPayload(session), cameraFeaturePayload(feature))
                }
            } else false
            if (synced) dao.updateCameraSyncState(session.id, "SYNCED")
            val savedSession = if (synced) session.copy(syncState = "SYNCED") else session
            _state.value = _state.value.copy(
                cameraSessions = if (storeHistory) {
                    listOf(savedSession) + _state.value.cameraSessions.filterNot { it.id == session.id }
                } else _state.value.cameraSessions,
                cameraFeatures = if (storeHistory) {
                    listOf(feature) + _state.value.cameraFeatures.filterNot { it.sessionId == feature.sessionId }
                } else _state.value.cameraFeatures,
                latestCameraPreview = if (storeHistory) null else features,
                syncState = if (storeHistory) syncStateLabel(
                    _state.value.copy(
                        cameraSessions = listOf(savedSession) + _state.value.cameraSessions.filterNot { it.id == session.id },
                    ),
                ) else _state.value.syncState,

                notice = if (!storeHistory) {
                    "Camera observations were used for this result only and were not saved to history."
                } else if (accepted) {
                    "Camera observations saved locally. No video or face identity is retained."
                } else {
                    "The camera capture did not meet quality requirements. Its observations were saved as incomplete; repeat when ready."
                },
            )
            onSaved()
        }
    }

    fun saveRecovery() {
        viewModelScope.launch {
            val ownerId = app.backendClient.currentAthleteId()
            val latestCheckIn = withContext(Dispatchers.IO) { dao.latestCheckIn(ownerId) }
            val latestSleep = withContext(Dispatchers.IO) { dao.latestSleep(ownerId) }
            val factors = mutableMapOf<String, Any>()
            val checkinValues = latestCheckIn?.let {
                factors["recovery_feeling"] = mapOf("value" to it.recoveryFeeling, "source" to "SELF_REPORTED")
                factors["fatigue"] = mapOf("value" to it.fatigue, "source" to "SELF_REPORTED")
                factors["soreness"] = mapOf("value" to it.soreness, "source" to "SELF_REPORTED")
                factors["stress"] = mapOf("value" to it.stress, "source" to "SELF_REPORTED")
                listOf(it.recoveryFeeling, 6 - it.fatigue, 6 - it.soreness, 6 - it.stress).average()
            }
            latestSleep?.let {
                factors["sleep_duration_minutes"] = mapOf("value" to it.durationMinutes, "source" to it.source)
            }
            val result = when {
                checkinValues == null -> "INSUFFICIENT_DATA"
                checkinValues >= 4 -> "GOOD"
                checkinValues >= 3 -> "MODERATE"
                else -> "LOW"
            }
            val record = RecoveryRecordEntity(
                id = UUID.randomUUID().toString(),
                ownerId = ownerId,
                date = LocalDate.now().toString(),
                recoveryState = result,
                supportingFactors = gson.toJson(factors),
                calculationVersion = "recovery-v1",
                createdAtMs = System.currentTimeMillis(),
                syncState = pendingOrLocal(),
            )
            withContext(Dispatchers.IO) { dao.saveRecovery(record) }
            if (record.syncState == "SYNC_PENDING") {
                syncSafely {
                    app.backendClient.syncWellbeingRecovery(recoveryPayload(record))
                    dao.updateRecoverySyncState(record.id, "SYNCED")
                }
            }
            _state.value = _state.value.copy(notice = "Recovery context saved with its supporting sources.")
            refresh()
        }
    }

    fun generateReport(reportType: String) {
        viewModelScope.launch {
            val ownerId = app.backendClient.currentAthleteId()
            val checkIn = withContext(Dispatchers.IO) { dao.latestCheckIn(ownerId) }
            val session = withContext(Dispatchers.IO) { dao.latestCameraSession(ownerId) }
            val cameraFeature = session?.let { withContext(Dispatchers.IO) { dao.cameraFeatures(it.id, ownerId) } }
            val sleep = withContext(Dispatchers.IO) { dao.latestSleep(ownerId) }
            val recovery = withContext(Dispatchers.IO) { dao.recoveryRecords(ownerId, 1).firstOrNull() }
            val data = WellbeingReportGenerator().generate(reportType, checkIn, session, cameraFeature, sleep, recovery)
            val report = WellbeingReportEntity(
                id = UUID.randomUUID().toString(),
                ownerId = ownerId,
                reportType = reportType,
                reportData = gson.toJson(data),
                sourceProvenance = gson.toJson(data.sourceProvenance.map { it.name }),
                limitations = gson.toJson(data.limitations),
                createdAtMs = data.generatedAtMs,
                syncState = pendingOrLocal(),
            )
            withContext(Dispatchers.IO) { dao.saveReport(report) }
            if (report.syncState == "SYNC_PENDING") {
                syncSafely {
                    app.backendClient.syncWellbeingReport(reportPayload(report))
                    dao.updateReportSyncState(report.id, "SYNCED")
                }
            }
            _state.value = _state.value.copy(notice = "Wellbeing report saved with explicit source provenance and limitations.")
            refresh()
        }
    }

    fun syncPending() {
        val ownerId = app.backendClient.currentAthleteId() ?: run {
            _state.value = _state.value.copy(notice = "Sign in to sync. Your wellbeing records remain on this device.")
            return
        }
        viewModelScope.launch {
            val dao = app.wellbeingDatabase.wellbeingDao()
            try {
                dao.pendingCheckIns(ownerId).forEach { record ->
                    app.backendClient.syncWellbeingCheckIn(checkInPayload(record))
                    dao.updateCheckInSyncState(record.id, "SYNCED")
                }
                dao.pendingSleepRecords(ownerId).forEach { record ->
                    app.backendClient.syncWellbeingSleep(sleepPayload(record))
                    dao.updateSleepSyncState(record.id, "SYNCED")
                }
                dao.pendingCameraSessions(ownerId).forEach { session ->
                    val features = dao.cameraFeatures(session.id, ownerId)
                        ?: error("A pending camera session has no feature record.")
                    app.backendClient.syncCameraWellbeingSession(
                        cameraSessionPayload(session),
                        cameraFeaturePayload(features),
                    )
                    dao.updateCameraSyncState(session.id, "SYNCED")
                }
                dao.pendingRecoveryRecords(ownerId).forEach { record ->
                    app.backendClient.syncWellbeingRecovery(recoveryPayload(record))
                    dao.updateRecoverySyncState(record.id, "SYNCED")
                }
                dao.pendingReports(ownerId).forEach { report ->
                    app.backendClient.syncWellbeingReport(reportPayload(report))
                    dao.updateReportSyncState(report.id, "SYNCED")
                }
                _state.value = _state.value.copy(notice = "Pending wellbeing data synchronized.")
            } catch (error: Exception) {
                _state.value = _state.value.copy(error = error.message ?: "Pending wellbeing data could not be synchronized.")
            }
            refresh()
        }
    }

    private fun pendingOrLocal(): String =
        if (app.backendClient.currentAthleteId() != null) "SYNC_PENDING" else "LOCAL_ONLY"

    private suspend fun syncSafely(operation: suspend () -> Unit): Boolean {
        try {
            operation()
            return true
        } catch (error: Exception) {
            _state.value = _state.value.copy(
                error = "Saved on this device; sync is pending. ${error.message ?: "The backend is unavailable."}",
            )
            return false
        }
    }

    private fun syncStateLabel(state: WellbeingUiState): String {
        val syncStates = state.checkIns.map { it.syncState } +
            state.sleepRecords.map { it.syncState } +
            state.cameraSessions.map { it.syncState } +
            state.recoveryRecords.map { it.syncState } +
            state.reports.map { it.syncState }
        return when {
            syncStates.any { it == "SYNC_PENDING" } -> "SYNC_PENDING"
            syncStates.any { it == "LOCAL_ONLY" } -> "LOCAL_ONLY"
            else -> "SYNCED"
        }
    }

    private fun checkInPayload(record: WellbeingCheckInEntity) = mapOf(
        "id" to record.id,
        "energy" to record.energy,
        "stress" to record.stress,
        "fatigue" to record.fatigue,
        "soreness" to record.soreness,
        "recovery_feeling" to record.recoveryFeeling,
        "note" to record.note,
        "source" to record.source,
    )

    private fun sleepPayload(record: SleepRecordEntity) = mapOf(
        "id" to record.id,
        "start_time" to Instant.ofEpochMilli(record.startAtMs).toString(),
        "end_time" to Instant.ofEpochMilli(record.endAtMs).toString(),
        "duration_minutes" to record.durationMinutes,
        "quality_rating" to record.qualityRating,
        "interruptions" to record.interruptions,
        "notes" to record.notes,
        "source" to record.source,
        "source_id" to record.sourceId,
    )

    private fun cameraSessionPayload(record: CameraWellbeingSessionEntity) = mapOf(
        "id" to record.id,
        "started_at" to Instant.ofEpochMilli(record.startedAtMs).toString(),
        "completed_at" to record.completedAtMs?.let { Instant.ofEpochMilli(it).toString() },
        "duration_seconds" to record.durationSeconds,
        "status" to record.status,
        "camera_facing" to record.cameraFacing,
        "capture_quality" to record.captureQuality,
        "valid_frame_ratio" to record.validFrameRatio,
        "face_presence_ratio" to record.facePresenceRatio,
        "multiple_face_frames" to record.multipleFaceFrames,
        "raw_video_retained" to false,
        "source" to record.source,
    )

    private fun cameraFeaturePayload(record: CameraWellbeingFeatureEntity) = mapOf(
        "id" to record.id,
        "face_presence_ratio" to record.facePresenceRatio,
        "face_position_stability" to record.facePositionStability,
        "head_movement_magnitude" to record.headMovementMagnitude,
        "head_movement_variability" to record.headMovementVariability,
        "head_orientation_range" to record.headOrientationRange,
        "eye_observation_summary" to record.eyeObservationRatio?.let { mapOf("observation_ratio" to it) },
        "smile_observation_summary" to record.smileObservationRatio?.let { mapOf("observation_ratio" to it) },
        "facial_feature_movement" to record.facialFeatureMovement,
        "face_detected_frames" to record.faceDetectedFrames,
        "valid_frames" to record.validFrames,
        "invalid_frames" to record.invalidFrames,
        "poor_lighting_frames" to record.poorLightingFrames,
        "face_out_of_frame_frames" to record.faceOutOfFrameFrames,
        "capture_quality" to record.captureQuality,
        "feature_schema_version" to record.featureSchemaVersion,
        "source" to record.source,
    )

    private fun recoveryPayload(record: RecoveryRecordEntity) = mapOf(
        "date" to record.date,
        "recovery_state" to record.recoveryState,
        "supporting_factors" to gson.fromJson(record.supportingFactors, Map::class.java),
        "calculation_version" to record.calculationVersion,
        "source" to record.source,
    )

    private fun reportPayload(record: WellbeingReportEntity) = mapOf(
        "id" to record.id,
        "report_type" to record.reportType,
        "report_data" to gson.fromJson(record.reportData, Map::class.java),
        "source_provenance" to gson.fromJson(record.sourceProvenance, List::class.java),
        "limitations" to gson.fromJson(record.limitations, List::class.java),
    )

    companion object {
        fun create(app: VitaPulseApplication): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T = WellbeingViewModel(app) as T
            }
    }
}
