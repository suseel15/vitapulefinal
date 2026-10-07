package app.vitapulse.android.core.healthconnect

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "health_data_records")
data class HealthDataEntity(
    @PrimaryKey val deduplicationKey: String,
    val source: String,
    val sourceRecordId: String,
    val sourceApplication: String,
    val dataType: String,
    val recordStartMs: Long,
    val recordEndMs: Long,
    val lastModifiedMs: Long,
    val syncedAtMs: Long,
    val payloadJson: String,
    val backendUploadedAtMs: Long?,
)

@Entity(tableName = "health_sync_cursors", primaryKeys = ["source", "dataType"])
data class HealthSyncCursorEntity(
    val source: String,
    val dataType: String,
    val lastSyncAtMs: Long,
    val lastRecordTimeMs: Long?,
)

@Entity(tableName = "health_sync_runs")
data class HealthSyncRunEntity(
    @PrimaryKey val id: String,
    val source: String,
    val startedAtMs: Long,
    val completedAtMs: Long?,
    val status: String,
    val recordsFound: Int,
    val recordsImported: Int,
    val recordsSkipped: Int,
    val recordsFailed: Int,
    val errorCode: String?,
)

@Dao
interface HealthDataDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertRecord(record: HealthDataEntity): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveCursor(cursor: HealthSyncCursorEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveSyncRun(run: HealthSyncRunEntity)

    @Query("SELECT * FROM health_data_records ORDER BY recordStartMs DESC LIMIT :limit")
    fun observeRecentRecords(limit: Int = 100): Flow<List<HealthDataEntity>>

    @Query("SELECT * FROM health_data_records WHERE dataType = :type ORDER BY recordEndMs DESC LIMIT :limit")
    fun observeRecordsByType(type: String, limit: Int = 500): Flow<List<HealthDataEntity>>

    @Query("SELECT * FROM health_data_records WHERE dataType = :type ORDER BY recordStartMs DESC LIMIT :limit")
    suspend fun records(type: String, limit: Int = 500): List<HealthDataEntity>

    @Query("SELECT * FROM health_data_records WHERE backendUploadedAtMs IS NULL ORDER BY syncedAtMs LIMIT :limit")
    suspend fun pendingBackendRecords(limit: Int = 500): List<HealthDataEntity>

    @Query("SELECT COUNT(*) FROM health_data_records WHERE backendUploadedAtMs IS NULL")
    fun observePendingBackendCount(): Flow<Int>

    @Query("UPDATE health_data_records SET backendUploadedAtMs = :uploadedAtMs WHERE deduplicationKey IN (:keys)")
    suspend fun markBackendUploaded(keys: List<String>, uploadedAtMs: Long)

    @Query("SELECT * FROM health_sync_cursors WHERE source = :source AND dataType = :type LIMIT 1")
    suspend fun cursor(source: String, type: String): HealthSyncCursorEntity?

    @Query("SELECT * FROM health_sync_runs ORDER BY startedAtMs DESC LIMIT :limit")
    fun observeSyncRuns(limit: Int = 50): Flow<List<HealthSyncRunEntity>>

    @Query("DELETE FROM health_data_records WHERE dataType = :type AND source = :source")
    suspend fun deleteRecords(type: String, source: String = "HEALTH_CONNECT")

    @Query("DELETE FROM health_data_records WHERE source = :source")
    suspend fun deleteAllRecords(source: String = "HEALTH_CONNECT")

    @Query("DELETE FROM health_sync_cursors WHERE source = :source")
    suspend fun deleteCursors(source: String = "HEALTH_CONNECT")

    @Query("DELETE FROM health_sync_runs WHERE source = :source")
    suspend fun deleteSyncRuns(source: String = "HEALTH_CONNECT")
}

@Database(
    entities = [HealthDataEntity::class, HealthSyncCursorEntity::class, HealthSyncRunEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class HealthDataDatabase : RoomDatabase() {
    abstract fun healthDataDao(): HealthDataDao
}
