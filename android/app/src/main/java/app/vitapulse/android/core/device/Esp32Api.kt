package app.vitapulse.android.core.device

import retrofit2.http.GET
import retrofit2.http.Query
import okhttp3.ResponseBody

interface Esp32Api {
    @GET("status")
    suspend fun getStatus(): Esp32StatusResponse

    @GET("data")
    suspend fun getSensorData(): Esp32SensorResponse

    @GET("exercise")
    suspend fun selectExercise(@Query("value") index: Int): ResponseBody

    @GET("reset")
    suspend fun resetExerciseCounter(): ResponseBody
}
