package app.vitapulse.android.core.device

data class Esp32StatusResponse(
    val device: String?,
    val wifi: Boolean?,
    val mpu6050: Boolean?,
    val ip: String?,
)
