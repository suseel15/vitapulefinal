package app.vitapulse.android.core.device

data class Esp32Device(
    val identifier: String,
    val sensorType: String = "MPU6050",
    val ipAddress: String,
    val transport: String = "HTTP",
    val firmwareProtocol: String = "VITAPULSE_STAGE_1_HTTP",
)
