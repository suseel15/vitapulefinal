package app.vitapulse.android.feature.wellbeing.data

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase

@Entity(tableName = "wellbeing_checkins")
data class WellbeingCheckInEntity(
    @PrimaryKey val id: String,
    val ownerId: String?,
    val energy: Int,
    val stress: Int,
    val fatigue: Int,
    val soreness: Int,
    val recoveryFeeling: Int,
    val moodSelfReport: Int?,
    val note: String?,
    val source: String = "SELF_REPORTED",
    val createdAtMs: Long,
    val updatedAtMs: Long,
    val syncState: String = "LOCAL_ONLY",
)

@Entity(tableName = "camera_wellbeing_sessions")
data class CameraWellbeingSessionEntity(
    @PrimaryKey val id: String,
    val ownerId: String?,
    val startedAtMs: Long,
    val completedAtMs: Long?,
    val durationSeconds: Int,
    val status: String,
    val cameraFacing: String = "FRONT",
    val captureQuality: String,
    val validFrameRatio: Double,
    val facePresenceRatio: Double,
    val multipleFaceFrames: Int,
    val rawVideoRetained: Boolean = false,
    val source: String = "CAMERA_OBSERVED",
    val syncState: String = "LOCAL_ONLY",
)

@Entity(tableName = "camera_wellbeing_features")
data class CameraWellbeingFeatureEntity(
    @PrimaryKey val id: String,
    val sessionId: String,
    val ownerId: String?,
    val facePresenceRatio: Double,
    val facePositionStability: String,
    val headMovementMagnitude: Double?,
    val headMovementVariability: Double?,
    val headOrientationRange: Double?,
    val eyeObservationRatio: Double?,
    val smileObservationRatio: Double?,
    val facialFeatureMovement: Double?,
    val faceDetectedFrames: Int,
    val validFrames: Int,
    val invalidFrames: Int,
    val poorLightingFrames: Int,
    val faceOutOfFrameFrames: Int,
    val captureQuality: String,
    val featureSchemaVersion: String,
    val source: String = "CAMERA_OBSERVED",
    val createdAtMs: Long,
)

@Entity(tableName = "wellbeing_sleep_records")
data class SleepRecordEntity(
    @PrimaryKey val id: String,
    val ownerId: String?,
    val startAtMs: Long,
    val endAtMs: Long,
    val durationMinutes: Int,
    val qualityRating: Int?,
    val interruptions: Int?,
    val notes: String?,
    val source: String,
    val sourceId: String?,
    val createdAtMs: Long,
    val syncState: String = "LOCAL_ONLY",
)

@Entity(tableName = "wellbeing_recovery_records")
data class RecoveryRecordEntity(
    @PrimaryKey val id: String,
    val ownerId: String?,
    val date: String,
    val recoveryState: String,
    val supportingFactors: String,
    val calculationVersion: String,
    val source: String = "CALCULATED",
    val createdAtMs: Long,
    val syncState: String = "LOCAL_ONLY",
)

@Entity(tableName = "wellbeing_reports")
data class WellbeingReportEntity(
    @PrimaryKey val id: String,
    val ownerId: String?,
    val reportType: String,
    val reportData: String,
    val sourceProvenance: String,
    val limitations: String,
    val createdAtMs: Long,
    val syncState: String = "LOCAL_ONLY",
)

@Dao
interface WellbeingDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveCheckIn(record: WellbeingCheckInEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveCameraSession(record: CameraWellbeingSessionEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveCameraFeatures(record: CameraWellbeingFeatureEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveSleep(record: SleepRecordEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveRecovery(record: RecoveryRecordEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveReport(record: WellbeingReportEntity)

    @Query("SELECT * FROM wellbeing_checkins WHERE (:ownerId IS NULL AND ownerId IS NULL) OR ownerId = :ownerId ORDER BY createdAtMs DESC LIMIT :limit")
    suspend fun checkIns(ownerId: String?, limit: Int = 100): List<WellbeingCheckInEntity>

    @Query("SELECT * FROM wellbeing_checkins WHERE (:ownerId IS NULL AND ownerId IS NULL) OR ownerId = :ownerId ORDER BY createdAtMs DESC LIMIT 1")
    suspend fun latestCheckIn(ownerId: String?): WellbeingCheckInEntity?

    @Query("SELECT * FROM camera_wellbeing_sessions WHERE (:ownerId IS NULL AND ownerId IS NULL) OR ownerId = :ownerId ORDER BY startedAtMs DESC LIMIT :limit")
    suspend fun cameraSessions(ownerId: String?, limit: Int = 100): List<CameraWellbeingSessionEntity>

    @Query("SELECT * FROM camera_wellbeing_sessions WHERE (:ownerId IS NULL AND ownerId IS NULL) OR ownerId = :ownerId ORDER BY startedAtMs DESC LIMIT 1")
    suspend fun latestCameraSession(ownerId: String?): CameraWellbeingSessionEntity?

    @Query("SELECT * FROM camera_wellbeing_features WHERE sessionId = :sessionId AND ((:ownerId IS NULL AND ownerId IS NULL) OR ownerId = :ownerId) LIMIT 1")
    suspend fun cameraFeatures(sessionId: String, ownerId: String?): CameraWellbeingFeatureEntity?

    @Query("SELECT * FROM wellbeing_sleep_records WHERE (:ownerId IS NULL AND ownerId IS NULL) OR ownerId = :ownerId ORDER BY startAtMs DESC LIMIT :limit")
    suspend fun sleepRecords(ownerId: String?, limit: Int = 100): List<SleepRecordEntity>

    @Query("SELECT * FROM wellbeing_sleep_records WHERE (:ownerId IS NULL AND ownerId IS NULL) OR ownerId = :ownerId ORDER BY startAtMs DESC LIMIT 1")
    suspend fun latestSleep(ownerId: String?): SleepRecordEntity?

    @Query("SELECT * FROM wellbeing_recovery_records WHERE (:ownerId IS NULL AND ownerId IS NULL) OR ownerId = :ownerId ORDER BY date DESC LIMIT :limit")
    suspend fun recoveryRecords(ownerId: String?, limit: Int = 100): List<RecoveryRecordEntity>

    @Query("SELECT * FROM wellbeing_reports WHERE (:ownerId IS NULL AND ownerId IS NULL) OR ownerId = :ownerId ORDER BY createdAtMs DESC LIMIT :limit")
    suspend fun reports(ownerId: String?, limit: Int = 100): List<WellbeingReportEntity>

    @Query("SELECT * FROM wellbeing_checkins WHERE ownerId = :ownerId AND syncState = 'SYNC_PENDING' ORDER BY createdAtMs ASC")
    suspend fun pendingCheckIns(ownerId: String): List<WellbeingCheckInEntity>

    @Query("SELECT * FROM wellbeing_sleep_records WHERE ownerId = :ownerId AND syncState = 'SYNC_PENDING' ORDER BY createdAtMs ASC")
    suspend fun pendingSleepRecords(ownerId: String): List<SleepRecordEntity>

    @Query("SELECT * FROM camera_wellbeing_sessions WHERE ownerId = :ownerId AND syncState = 'SYNC_PENDING' ORDER BY startedAtMs ASC")
    suspend fun pendingCameraSessions(ownerId: String): List<CameraWellbeingSessionEntity>

    @Query("SELECT * FROM wellbeing_recovery_records WHERE ownerId = :ownerId AND syncState = 'SYNC_PENDING' ORDER BY createdAtMs ASC")
    suspend fun pendingRecoveryRecords(ownerId: String): List<RecoveryRecordEntity>

    @Query("SELECT * FROM wellbeing_reports WHERE ownerId = :ownerId AND syncState = 'SYNC_PENDING' ORDER BY createdAtMs ASC")
    suspend fun pendingReports(ownerId: String): List<WellbeingReportEntity>

    @Query("UPDATE wellbeing_checkins SET syncState = :syncState WHERE id = :id")
    suspend fun updateCheckInSyncState(id: String, syncState: String)

    @Query("UPDATE wellbeing_sleep_records SET syncState = :syncState WHERE id = :id")
    suspend fun updateSleepSyncState(id: String, syncState: String)

    @Query("UPDATE camera_wellbeing_sessions SET syncState = :syncState WHERE id = :id")
    suspend fun updateCameraSyncState(id: String, syncState: String)

    @Query("UPDATE wellbeing_recovery_records SET syncState = :syncState WHERE id = :id")
    suspend fun updateRecoverySyncState(id: String, syncState: String)

    @Query("UPDATE wellbeing_reports SET syncState = :syncState WHERE id = :id")
    suspend fun updateReportSyncState(id: String, syncState: String)
}

@Database(
    entities = [
        WellbeingCheckInEntity::class,
        CameraWellbeingSessionEntity::class,
        CameraWellbeingFeatureEntity::class,
        SleepRecordEntity::class,
        RecoveryRecordEntity::class,
        WellbeingReportEntity::class,
    ],
    version = 1,
    exportSchema = false,
)
abstract class WellbeingDatabase : RoomDatabase() {
    abstract fun wellbeingDao(): WellbeingDao
}
