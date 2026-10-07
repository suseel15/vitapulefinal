package app.vitapulse.android.core.healthconnect

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.time.Duration
import java.time.Instant

fun buildHealthConnectUploadRequest(
    records: List<HealthDataEntity>,
): Map<String, Any> {
    require(records.isNotEmpty() && records.size <= MAX_UPLOAD_RECORDS) {
        "Health Connect uploads must contain between 1 and $MAX_UPLOAD_RECORDS records."
    }
    require(records.all { it.source == "HEALTH_CONNECT" }) {
        "Only Health Connect records may be uploaded through this endpoint."
    }
    val start = records.minOf { it.recordStartMs }
    val end = maxOf(records.maxOf { it.recordEndMs }, start + 1)
    require(Duration.ofMillis(end - start) <= MAX_UPLOAD_RANGE) {
        "Health Connect upload batches cannot span more than 30 days."
    }
    val dataTypes = records.map { it.dataType }.distinct()
    return mapOf(
        "sources" to listOf("HEALTH_CONNECT"),
        "data_types" to dataTypes,
        "from" to Instant.ofEpochMilli(start).toString(),
        "to" to Instant.ofEpochMilli(end).toString(),
        "records" to records.map(::toSummaryRecord),
    )
}

private fun toSummaryRecord(record: HealthDataEntity): Map<String, Any?> {
    val payload = JsonParser.parseString(record.payloadJson).asJsonObject
    val value = when (HealthDataType.valueOf(record.dataType)) {
        HealthDataType.SLEEP -> mapOf(
            "duration_minutes" to payload.requiredInt("durationMinutes"),
        )
        HealthDataType.HEART_RATE -> {
            val samples = payload.getAsJsonArray("samples")
                ?: error("A heart-rate record has no sample summary.")
            require(samples.size() in 1..MAX_HEART_RATE_SAMPLES) {
                "A heart-rate record has an unsupported sample count."
            }
            val bpmValues = samples.map { it.asJsonObject.get("beatsPerMinute").asLong }
            require(bpmValues.all { it in 25L..250L }) {
                "A heart-rate record contains an unsupported value."
            }
            mapOf(
                "average_bpm" to bpmValues.average(),
                "sample_count" to bpmValues.size,
                "measurement_type" to "UNKNOWN",
            )
        }
        HealthDataType.STEPS -> mapOf("count" to payload.requiredLong("count"))
        HealthDataType.EXERCISE -> mapOf(
            "exercise_type" to payload.requiredInt("exerciseType"),
            "duration_minutes" to Duration.ofMillis(record.recordEndMs - record.recordStartMs).toMinutes().toInt(),
            "title" to payload.get("title")?.takeUnless { it.isJsonNull }?.asString,
        )
        HealthDataType.OXYGEN_SATURATION -> mapOf(
            "percentage" to payload.requiredDouble("percentage").times(100.0),
        )
    }
    return mapOf(
        "data_type" to record.dataType,
        "source_record_id" to record.sourceRecordId,
        "source_application" to record.sourceApplication,
        "start_time" to Instant.ofEpochMilli(record.recordStartMs).toString(),
        "end_time" to Instant.ofEpochMilli(record.recordEndMs).toString(),
        "last_modified_at" to Instant.ofEpochMilli(record.lastModifiedMs).toString(),
        "value" to value,
    )
}

private fun JsonObject.requiredInt(field: String): Int =
    get(field)?.takeUnless { it.isJsonNull }?.asInt ?: error("A health record is missing $field.")

private fun JsonObject.requiredLong(field: String): Long =
    get(field)?.takeUnless { it.isJsonNull }?.asLong ?: error("A health record is missing $field.")

private fun JsonObject.requiredDouble(field: String): Double =
    get(field)?.takeUnless { it.isJsonNull }?.asDouble ?: error("A health record is missing $field.")

private const val MAX_UPLOAD_RECORDS = 500
private const val MAX_HEART_RATE_SAMPLES = 1_000_000
private val MAX_UPLOAD_RANGE = Duration.ofDays(30)
