package app.vitapulse.android.core.device

data class Esp32SensorResponse(
    val mpu: Boolean?,
    val ax: Double?,
    val ay: Double?,
    val az: Double?,
    val gx: Double?,
    val gy: Double?,
    val gz: Double?,
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
