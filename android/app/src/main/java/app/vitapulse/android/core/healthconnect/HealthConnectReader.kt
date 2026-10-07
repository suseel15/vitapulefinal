package app.vitapulse.android.core.healthconnect

import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.records.ExerciseSessionRecord as HcExerciseSessionRecord
import androidx.health.connect.client.records.HeartRateRecord as HcHeartRateRecord
import androidx.health.connect.client.records.OxygenSaturationRecord as HcOxygenSaturationRecord
import androidx.health.connect.client.records.SleepSessionRecord as HcSleepSessionRecord
import androidx.health.connect.client.records.StepsRecord as HcStepsRecord
import androidx.health.connect.client.records.Record
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant

class HealthConnectReader(private val client: HealthConnectClient) {
    suspend fun read(type: HealthDataType, start: Instant, end: Instant): List<UnifiedHealthRecord> {
        require(start < end) { "Health Connect queries require a bounded, increasing time range." }
        return when (type) {
            HealthDataType.SLEEP -> readPages<HcSleepSessionRecord>(start, end).map { record ->
                SleepRecord(
                    sourceId = record.metadata.id,
                    sourceApplication = record.metadata.dataOrigin.packageName,
                    startTime = record.startTime,
                    endTime = record.endTime,
                    lastModified = record.metadata.lastModifiedTime,
                    durationMinutes = java.time.Duration.between(record.startTime, record.endTime).toMinutes(),
                    stages = record.stages.map { stage ->
                        SleepStageData(stage.stage, stage.startTime, stage.endTime)
                    },
                )
            }
            HealthDataType.HEART_RATE -> readPages<HcHeartRateRecord>(start, end).map { record ->
                HeartRateRecord(
                    sourceId = record.metadata.id,
                    sourceApplication = record.metadata.dataOrigin.packageName,
                    startTime = record.startTime,
                    endTime = record.endTime,
                    lastModified = record.metadata.lastModifiedTime,
                    samples = record.samples.map { sample ->
                        HeartRateSample(sample.time, sample.beatsPerMinute)
                    },
                )
            }
            HealthDataType.STEPS -> readPages<HcStepsRecord>(start, end).map { record ->
                StepsRecord(
                    sourceId = record.metadata.id,
                    sourceApplication = record.metadata.dataOrigin.packageName,
                    startTime = record.startTime,
                    endTime = record.endTime,
                    lastModified = record.metadata.lastModifiedTime,
                    count = record.count,
                )
            }
            HealthDataType.EXERCISE -> readPages<HcExerciseSessionRecord>(start, end).map { record ->
                ExerciseRecord(
                    sourceId = record.metadata.id,
                    sourceApplication = record.metadata.dataOrigin.packageName,
                    startTime = record.startTime,
                    endTime = record.endTime,
                    lastModified = record.metadata.lastModifiedTime,
                    exerciseType = record.exerciseType,
                    title = record.title,
                )
            }
            HealthDataType.OXYGEN_SATURATION -> readPages<HcOxygenSaturationRecord>(start, end).map { record ->
                OxygenSaturationRecord(
                    sourceId = record.metadata.id,
                    sourceApplication = record.metadata.dataOrigin.packageName,
                    startTime = record.time,
                    endTime = record.time,
                    lastModified = record.metadata.lastModifiedTime,
                    percentage = record.percentage.value,
                )
            }
        }
    }

    private suspend inline fun <reified T : Record> readPages(
        start: Instant,
        end: Instant,
    ): List<T> {
        val results = mutableListOf<T>()
        var pageToken: String? = null
        do {
            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = T::class,
                    timeRangeFilter = TimeRangeFilter.between(start, end),
                    pageSize = PAGE_SIZE,
                    pageToken = pageToken,
                ),
            )
            results += response.records
            pageToken = response.pageToken
        } while (pageToken != null)
        return results
    }

    private companion object {
        const val PAGE_SIZE = 500
    }
}
