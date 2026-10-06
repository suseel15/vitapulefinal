package app.vitapulse.android.core.device

import retrofit2.http.GET

interface Esp32Api {
    @GET("status")
    suspend fun getStatus(): Esp32StatusResponse

    @GET("data")
    suspend fun getSensorData(): Esp32SensorResponse
}
