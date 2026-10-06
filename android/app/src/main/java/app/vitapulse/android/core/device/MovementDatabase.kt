package app.vitapulse.android.core.device

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.migration.Migration
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.Transaction
import androidx.sqlite.db.SupportSQLiteDatabase
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "movement_sessions")
data class MovementSessionEntity(
    @PrimaryKey val id: String,
    val exerciseName: String,
    val exerciseId: String?,
    val deviceIdentifier: String,
    val registeredDeviceId: String?,
    val sensorType: String,
    val transport: String,
    val source: String,
    val sensorPlacement: String,
    val targetRepetitions: Int,
    val backendSessionId: String?,
    val status: String,
    val startedAtMs: Long,
    val endedAtMs: Long?,
    val sampleCount: Int,
    val successfulRequests: Int,
    val failedRequests: Int,
    val invalidSamples: Int,
    val averageLatencyMs: Double?,
    val measuredRateHz: Double?,
    val movementQuality: String,
    val stability: String,
    val smoothness: String,
    val fatigueSignal: String,
    val repetitions: Int,
    val syncState: String,
    val ownerId: String?,
    val consistency: String?,
    val sensorQuality: String?,
    val recognition: String?,
    val recognizedExercise: String?,
    val modelName: String?,
    val modelVersion: String?,
    val baselineStatus: String?,
    val anomalyCount: Int?,
)

@Entity(tableName = "movement_samples", primaryKeys = ["sessionId", "appTimestamp"])
data class MovementSampleEntity(
    val sessionId: String,
    val appTimestamp: Long,
    val ax: Double,
    val ay: Double,
    val az: Double,
    val gx: Double,
    val gy: Double,
    val gz: Double,
)

@Entity(tableName = "session_calibrations")
data class SessionCalibrationEntity(
    @PrimaryKey val calibrationId: String,
    val sessionId: String,
    val timestampMs: Long,
    val sensorPlacement: String,
    val gyroBiasX: Double,
    val gyroBiasY: Double,
    val gyroBiasZ: Double,
    val baselineAx: Double,
    val baselineAy: Double,
    val baselineAz: Double,
    val signalVariance: Double,
    val quality: String,
    val source: String,
)

@Entity(tableName = "movement_repetitions", primaryKeys = ["sessionId", "repNumber"])
data class MovementRepetitionEntity(
    val sessionId: String,
    val repNumber: Int,
    val startedAtMs: Long,
    val endedAtMs: Long,
    val durationMs: Long,
    val quality: String,
    val amplitude: Double,
    val smoothness: Double,
    val source: String,
)

@Entity(tableName = "movement_baselines", primaryKeys = ["ownerId", "exerciseId", "sensorPlacement"])
data class MovementBaselineEntity(
    val ownerId: String,
    val exerciseId: String,
    val sensorPlacement: String,
    val baselineVersion: Int,
    val sessionCount: Int,
    val repetitionCount: Int,
    val meanDurationMs: Double,
    val durationStandardDeviationMs: Double,
    val meanAmplitude: Double,
    val updatedAtMs: Long,
    val status: String,
)

@Entity(tableName = "movement_events")
data class MovementEventEntity(
    @PrimaryKey val id: String,
    val sessionId: String,
    val timestampMs: Long,
    val eventType: String,
    val severity: String,
    val description: String,
    val source: String,
)

@Entity(tableName = "movement_predictions")
data class MovementPredictionEntity(
    @PrimaryKey val id: String,
    val sessionId: String,
    val exercise: String,
    val modelName: String,
    val modelVersion: String,
    val featureSchemaVersion: String,
    val timestampMs: Long,
    val source: String,
)

@Dao
interface MovementDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveSession(session: MovementSessionEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveCalibration(calibration: SessionCalibrationEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveSamples(samples: List<MovementSampleEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveRepetitions(repetitions: List<MovementRepetitionEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveBaseline(baseline: MovementBaselineEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveEvent(event: MovementEventEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun savePrediction(prediction: MovementPredictionEntity)

    @Query("SELECT * FROM movement_sessions ORDER BY startedAtMs DESC")
    fun sessions(): Flow<List<MovementSessionEntity>>

    @Query("SELECT * FROM movement_sessions WHERE id = :sessionId")
    suspend fun session(sessionId: String): MovementSessionEntity?

    @Query("SELECT * FROM movement_sessions WHERE status = 'COMPLETED' AND syncState IN ('SYNC_PENDING', 'SYNC_FAILED')")
    suspend fun pendingSessions(): List<MovementSessionEntity>

    @Query("SELECT * FROM movement_samples WHERE sessionId = :sessionId ORDER BY appTimestamp DESC LIMIT :limit")
    suspend fun recentSamples(sessionId: String, limit: Int = 600): List<MovementSampleEntity>

    @Query("SELECT * FROM movement_repetitions WHERE sessionId = :sessionId ORDER BY repNumber ASC")
    suspend fun repetitions(sessionId: String): List<MovementRepetitionEntity>

    @Query("SELECT * FROM movement_events WHERE sessionId = :sessionId ORDER BY timestampMs ASC")
    suspend fun events(sessionId: String): List<MovementEventEntity>

    @Query("SELECT * FROM movement_predictions WHERE sessionId = :sessionId ORDER BY timestampMs DESC LIMIT 1")
    suspend fun latestPrediction(sessionId: String): MovementPredictionEntity?

    @Query("SELECT r.* FROM movement_repetitions r JOIN movement_sessions s ON r.sessionId = s.id WHERE s.ownerId = :ownerId AND s.exerciseId = :exerciseId AND s.sensorPlacement = :sensorPlacement AND s.status = 'COMPLETED' AND s.source = 'LIVE_SENSOR' AND s.sensorQuality IN ('EXCELLENT', 'GOOD') AND s.sampleCount >= :minimumSamples ORDER BY s.startedAtMs DESC LIMIT :limit")
    suspend fun eligibleBaselineRepetitions(
        ownerId: String,
        exerciseId: String,
        sensorPlacement: String,
        minimumSamples: Int = 20,
        limit: Int = 2000,
    ): List<MovementRepetitionEntity>

    @Query("SELECT * FROM movement_sessions WHERE ownerId = :ownerId AND exerciseId = :exerciseId AND sensorPlacement = :sensorPlacement AND status = 'COMPLETED' AND source = 'LIVE_SENSOR' AND sensorQuality IN ('EXCELLENT', 'GOOD') AND sampleCount >= :minimumSamples ORDER BY startedAtMs DESC LIMIT :limit")
    suspend fun eligibleBaselineSessions(
        ownerId: String,
        exerciseId: String,
        sensorPlacement: String,
        minimumSamples: Int = 20,
        limit: Int = 100,
    ): List<MovementSessionEntity>

    @Query("SELECT * FROM movement_baselines WHERE ownerId = :ownerId AND exerciseId = :exerciseId AND sensorPlacement = :sensorPlacement LIMIT 1")
    suspend fun movementBaseline(ownerId: String, exerciseId: String, sensorPlacement: String): MovementBaselineEntity?

    @Query("DELETE FROM movement_samples WHERE sessionId = :sessionId AND appTimestamp NOT IN (SELECT appTimestamp FROM movement_samples WHERE sessionId = :sessionId ORDER BY appTimestamp DESC LIMIT :limit)")
    suspend fun trimSamples(sessionId: String, limit: Int = 600)

    @Query("DELETE FROM movement_samples WHERE sessionId = :sessionId")
    suspend fun deleteSamples(sessionId: String)

    @Transaction
    suspend fun saveBoundedSamples(sessionId: String, samples: List<MovementSampleEntity>) {
        if (samples.isNotEmpty()) saveSamples(samples)
        trimSamples(sessionId)
    }
}

@Database(
    entities = [
        MovementSessionEntity::class,
        MovementSampleEntity::class,
        SessionCalibrationEntity::class,
        MovementRepetitionEntity::class,
        MovementBaselineEntity::class,
        MovementEventEntity::class,
        MovementPredictionEntity::class,
    ],
    version = 2,
    exportSchema = false,
)
abstract class MovementDatabase : RoomDatabase() {
    abstract fun movementDao(): MovementDao

    companion object {
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                listOf(
                    "ownerId TEXT",
                    "consistency TEXT",
                    "sensorQuality TEXT",
                    "recognition TEXT",
                    "recognizedExercise TEXT",
                    "modelName TEXT",
                    "modelVersion TEXT",
                    "baselineStatus TEXT",
                    "anomalyCount INTEGER",
                ).forEach { column ->
                    db.execSQL("ALTER TABLE movement_sessions ADD COLUMN $column")
                }
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS movement_repetitions (" +
                        "sessionId TEXT NOT NULL, repNumber INTEGER NOT NULL, startedAtMs INTEGER NOT NULL, " +
                        "endedAtMs INTEGER NOT NULL, durationMs INTEGER NOT NULL, quality TEXT NOT NULL, " +
                        "amplitude REAL NOT NULL, smoothness REAL NOT NULL, source TEXT NOT NULL, " +
                        "PRIMARY KEY(sessionId, repNumber))",
                )
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS movement_baselines (" +
                        "ownerId TEXT NOT NULL, exerciseId TEXT NOT NULL, sensorPlacement TEXT NOT NULL, " +
                        "baselineVersion INTEGER NOT NULL, sessionCount INTEGER NOT NULL, repetitionCount INTEGER NOT NULL, " +
                        "meanDurationMs REAL NOT NULL, durationStandardDeviationMs REAL NOT NULL, meanAmplitude REAL NOT NULL, " +
                        "updatedAtMs INTEGER NOT NULL, status TEXT NOT NULL, " +
                        "PRIMARY KEY(ownerId, exerciseId, sensorPlacement))",
                )
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS movement_events (" +
                        "id TEXT NOT NULL PRIMARY KEY, sessionId TEXT NOT NULL, timestampMs INTEGER NOT NULL, " +
                        "eventType TEXT NOT NULL, severity TEXT NOT NULL, description TEXT NOT NULL, source TEXT NOT NULL)",
                )
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS movement_predictions (" +
                        "id TEXT NOT NULL PRIMARY KEY, sessionId TEXT NOT NULL, exercise TEXT NOT NULL, modelName TEXT NOT NULL, " +
                        "modelVersion TEXT NOT NULL, featureSchemaVersion TEXT NOT NULL, timestampMs INTEGER NOT NULL, source TEXT NOT NULL)",
                )
            }
        }
    }
}

data class SessionCalibration(
    val calibrationId: String,
    val sessionId: String,
    val timestampMs: Long,
    val sensorPlacement: String,
    val gyroBiasX: Double,
    val gyroBiasY: Double,
    val gyroBiasZ: Double,
    val baselineAx: Double,
    val baselineAy: Double,
    val baselineAz: Double,
    val signalVariance: Double,
    val quality: String,
    val source: String = "LIVE_SENSOR",
) {
    val baselineMagnitude: Double get() = kotlin.math.sqrt(
        baselineAx * baselineAx + baselineAy * baselineAy + baselineAz * baselineAz,
    )

    fun asEntity() = SessionCalibrationEntity(
        calibrationId, sessionId, timestampMs, sensorPlacement,
        gyroBiasX, gyroBiasY, gyroBiasZ,
        baselineAx, baselineAy, baselineAz, signalVariance, quality, source,
    )
}
