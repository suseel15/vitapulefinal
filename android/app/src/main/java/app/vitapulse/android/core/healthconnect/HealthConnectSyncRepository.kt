package app.vitapulse.android.core.healthconnect

import androidx.room.withTransaction
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.JsonDeserializer
import com.google.gson.JsonPrimitive
import com.google.gson.JsonSerializer
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.UUID

fun interface HealthDataProvider {
    suspend fun read(type: HealthDataType, start: Instant, end: Instant): List<UnifiedHealthRecord>
}

interface WearableDataProvider {
    suspend fun getStatus(): WearableStatus
    suspend fun sync(): HealthDataSyncResult
    suspend fun getAvailableDataTypes(): Set<HealthDataType>
}

data class WearableStatus(
    val status: String,
    val model: String,
    val companionAppInstalled: Boolean,
    val lastSyncAt: Instant?,
    val availableDataTypes: Set<HealthDataType>,
)

class HealthConnectSyncRepository(
    private val database: HealthDataDatabase,
    private val permissions: HealthConnectPermissionManager,
    private val provider: HealthDataProvider,
    private val gson: Gson = healthDataGson(),
) {
    private val dao = database.healthDataDao()

    suspend fun sync(types: Set<HealthDataType>, now: Instant = Instant.now()): HealthDataSyncResult {
        val startedAt = now
        val runId = UUID.randomUUID().toString()
        var found = 0
        var imported = 0
        var skipped = 0
        var pending = 0
        val errors = linkedMapOf<HealthDataType, String>()
        dao.saveSyncRun(
            HealthSyncRunEntity(
                id = runId,
                source = "HEALTH_CONNECT",
                startedAtMs = startedAt.toEpochMilli(),
                completedAtMs = null,
                status = HealthSyncStatus.SYNCING.name,
                recordsFound = 0,
                recordsImported = 0,
                recordsSkipped = 0,
                recordsFailed = 0,
                errorCode = null,
            ),
        )

        val granted = permissions.grantedPermissions()
        for (type in types) {
            if (permissions.requiredPermissions(setOf(type)).any { it !in granted }) {
                errors[type] = "PERMISSION_REQUIRED"
                continue
            }
            val previous = dao.cursor("HEALTH_CONNECT", type.name)
            val initialStart = now.minus(type.historyDays, ChronoUnit.DAYS)
            val start = previous?.lastSyncAtMs?.let {
                Instant.ofEpochMilli(it).minus(OVERLAP_HOURS, ChronoUnit.HOURS).coerceAtLeast(initialStart)
            } ?: initialStart
            try {
                val records = provider.read(type, start, now).filter { it.dataType == type }
                found += records.size
                var typeImported = 0
                var latestRecordTime: Long? = previous?.lastRecordTimeMs
                database.withTransaction {
                    records.forEach { record ->
                        if (!record.isValid()) {
                            errors[type] = "INVALID_RECORD"
                            return@forEach
                        }
                        val entity = record.toEntity(now, gson)
                        if (dao.insertRecord(entity) == -1L) {
                            skipped++
                        } else {
                            imported++
                            typeImported++
                            latestRecordTime = maxOf(latestRecordTime ?: Long.MIN_VALUE, entity.recordEndMs)
                            pending++
                        }
                    }
                    dao.saveCursor(
                        HealthSyncCursorEntity(
                            source = "HEALTH_CONNECT",
                            dataType = type.name,
                            lastSyncAtMs = now.toEpochMilli(),
                            lastRecordTimeMs = latestRecordTime,
                        ),
                    )
                }
                if (records.isEmpty() && type !in errors) errors[type] = "NO_DATA"
                if (typeImported == 0 && records.isNotEmpty()) skipped += 0
            } catch (error: SecurityException) {
                errors[type] = "PERMISSION_REQUIRED"
            } catch (error: java.io.IOException) {
                errors[type] = "SOURCE_UNAVAILABLE"
            }
        }

        val status = when {
            errors.isEmpty() && imported > 0 -> HealthSyncStatus.SYNCED
            errors.isNotEmpty() && (imported > 0 || skipped > 0) -> HealthSyncStatus.PARTIAL
            errors.values.all { it == "NO_DATA" } -> HealthSyncStatus.NO_DATA
            errors.values.all { it == "PERMISSION_REQUIRED" } -> HealthSyncStatus.PERMISSION_REQUIRED
            errors.isNotEmpty() -> HealthSyncStatus.FAILED
            else -> HealthSyncStatus.NO_DATA
        }
        val result = HealthDataSyncResult(status, found, imported, skipped, pending, errors, now)
        dao.saveSyncRun(
            HealthSyncRunEntity(
                id = runId,
                source = "HEALTH_CONNECT",
                startedAtMs = startedAt.toEpochMilli(),
                completedAtMs = now.toEpochMilli(),
                status = status.name,
                recordsFound = found,
                recordsImported = imported,
                recordsSkipped = skipped,
                recordsFailed = errors.count { it.value != "NO_DATA" },
                errorCode = errors.values.firstOrNull { it != "NO_DATA" },
            ),
        )
        return result
    }

    suspend fun deleteType(type: HealthDataType) {
        dao.deleteRecords(type.name)
        dao.saveCursor(
            HealthSyncCursorEntity(
                source = "HEALTH_CONNECT",
                dataType = type.name,
                lastSyncAtMs = 0,
                lastRecordTimeMs = null,
            ),
        )
    }

    suspend fun deleteAllHealthConnectData() {
        dao.deleteAllRecords()
        dao.deleteCursors()
        dao.deleteSyncRuns()
    }

    suspend fun pendingBackendUpload(limit: Int = UPLOAD_BATCH_SIZE): List<HealthDataEntity> =
        dao.pendingBackendRecords(limit)

    suspend fun markBackendUploaded(records: List<HealthDataEntity>, uploadedAt: Instant = Instant.now()) {
        if (records.isEmpty()) return
        dao.markBackendUploaded(records.map(HealthDataEntity::deduplicationKey), uploadedAt.toEpochMilli())
    }

    suspend fun uploadPendingBatch(upload: suspend (Map<String, Any>) -> Boolean): Boolean {
        val pending = dao.pendingBackendRecords(UPLOAD_BATCH_SIZE).sortedBy(HealthDataEntity::recordStartMs)
        if (pending.isEmpty()) return false
        val firstStart = pending.first().recordStartMs
        val latestAllowed = firstStart + MAX_BACKEND_RANGE_MS
        val batch = pending.filter { it.recordEndMs <= latestAllowed }.take(UPLOAD_BATCH_SIZE)
        check(batch.isNotEmpty()) { "A pending health record cannot fit in the supported upload window." }
        if (!upload(buildHealthConnectUploadRequest(batch))) return false
        markBackendUploaded(batch)
        return batch.size == UPLOAD_BATCH_SIZE
    }

    private fun UnifiedHealthRecord.toEntity(now: Instant, gson: Gson) = HealthDataEntity(
        deduplicationKey = deduplicationKey(),
        source = source,
        sourceRecordId = sourceId,
        sourceApplication = sourceApplication,
        dataType = dataType.name,
        recordStartMs = startTime.toEpochMilli(),
        recordEndMs = endTime.toEpochMilli(),
        lastModifiedMs = lastModified.toEpochMilli(),
        syncedAtMs = now.toEpochMilli(),
        payloadJson = payloadJson(gson),
        backendUploadedAtMs = null,
    )

    private companion object {
        const val OVERLAP_HOURS = 24L
        const val UPLOAD_BATCH_SIZE = 500
        const val MAX_BACKEND_RANGE_MS = 30L * 24 * 60 * 60 * 1000
    }
}

private fun Instant.coerceAtLeast(minimum: Instant): Instant = if (isBefore(minimum)) minimum else this

private fun healthDataGson(): Gson = GsonBuilder()
    .registerTypeAdapter(
        Instant::class.java,
        JsonSerializer<Instant> { instant, _, _ -> JsonPrimitive(instant.toString()) },
    )
    .registerTypeAdapter(
        Instant::class.java,
        JsonDeserializer<Instant> { json, _, _ -> Instant.parse(json.asString) },
    )
    .create()
