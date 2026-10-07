package app.vitapulse.android.core.device

data class Esp32SensorResponse(
    val mpu: Boolean?,
    val ax: Double?,
    val ay: Double?,
    val az: Double?,
    val gx: Double?,
    val gy: Double?,
    val gz: Double?,
    val exercise: String? = null,
    val reps: Int? = null,
    val phase: String? = null,
    val motion: String? = null,
)

data class Esp32Exercise(
    val index: Int,
    val name: String,
)

val ESP32_EXERCISES = listOf(
    Esp32Exercise(0, "Bicep Curl"),
    Esp32Exercise(1, "Hammer Curl"),
    Esp32Exercise(2, "Dumbbell Row"),
    Esp32Exercise(3, "Wrist Curl"),
    Esp32Exercise(4, "Reverse Wrist Curl"),
    Esp32Exercise(5, "Lateral Raise"),
    Esp32Exercise(6, "Front Raise"),
    Esp32Exercise(7, "Shoulder Press"),
    Esp32Exercise(8, "Tricep Extension"),
    Esp32Exercise(9, "Tricep Kickback"),
)

enum class SensorSource { LIVE_SENSOR, SIMULATION, MANUAL }

data class MovementSample(
    val appTimestamp: Long,
    val ax: Double,
    val ay: Double,
    val az: Double,
    val gx: Double,
    val gy: Double,
    val gz: Double,
    val source: SensorSource,
    val deviceId: String,
    val sensorType: String,
    val transport: String,
    val exerciseName: String? = null,
    val exerciseRepetitions: Int? = null,
    val exercisePhase: String? = null,
    val exerciseMotion: String? = null,
) {
    val accelerationMagnitude: Double get() = kotlin.math.sqrt(ax * ax + ay * ay + az * az)
    val gyroscopeMagnitude: Double get() = kotlin.math.sqrt(gx * gx + gy * gy + gz * gz)
}

enum class MovementConnectionState {
    DISCONNECTED,
    REQUESTING_WIFI,
    CONNECTING,
    CONNECTED,
    DEVICE_REACHABLE,
    SENSOR_CONNECTED,
    DEGRADED,
    RECONNECTING,
    NETWORK_PERMISSION_REQUIRED,
    WIFI_CONNECTION_FAILED,
    DEVICE_UNREACHABLE,
    SENSOR_UNAVAILABLE,
    ERROR,
    SIMULATION,
}

data class SensorDiagnostics(
    val successfulRequests: Long = 0,
    val failedRequests: Long = 0,
    val invalidSamples: Long = 0,
    val timeouts: Long = 0,
    val staleReadings: Long = 0,
    val averageLatencyMs: Double? = null,
    val maxLatencyMs: Long = 0,
    val measuredRateHz: Double? = null,
    val lastSuccessAtMs: Long? = null,
    val lastError: String? = null,
    val internetAvailable: Boolean = false,
)

sealed interface MovementDataSourceError {
    data object SensorUnavailable : MovementDataSourceError
    data object InvalidSample : MovementDataSourceError
    data object DeviceUnreachable : MovementDataSourceError
    data object StaleData : MovementDataSourceError
}
