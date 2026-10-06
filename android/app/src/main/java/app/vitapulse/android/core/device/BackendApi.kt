package app.vitapulse.android.core.device

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path

data class BackendEnvelope<T>(val success: Boolean, val data: T?, val error: BackendError?)
data class BackendError(val code: String?, val message: String?)
data class ProfileResponse(val profile: Profile)
data class Profile(val id: String, val role: String, @SerializedName("display_name") val displayName: String?)

data class SupabaseSignInResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("expires_in") val expiresIn: Long,
)

data class DeviceRegistrationRequest(
    @SerializedName("device_identifier") val deviceIdentifier: String,
    @SerializedName("device_type") val deviceType: String = "ESP32",
    @SerializedName("sensor_type") val sensorType: String = "MPU6050",
    val transport: String = "HTTP",
    val ip: String,
    @SerializedName("firmware_protocol") val firmwareProtocol: String = "VITAPULSE_STAGE_1_HTTP",
)

data class BackendMovementSession(
    val id: String,
    @SerializedName("athlete_id") val athleteId: String?,
    @SerializedName("device_id") val deviceId: String?,
    val status: String,
)

data class RehabSessionResponse(val session: BackendMovementSession)

data class MovementSummaryRequest(
    val source: String = "LIVE_SENSOR",
    @SerializedName("sensor_placement") val sensorPlacement: String,
    @SerializedName("sample_count") val sampleCount: Int,
    @SerializedName("target_repetitions") val targetRepetitions: Int?,
    @SerializedName("completed_repetitions") val completedRepetitions: Int,
    @SerializedName("movement_quality") val movementQuality: String,
    val stability: String,
    val smoothness: String,
    @SerializedName("fatigue_signal") val fatigueSignal: String,
    @SerializedName("session_duration_seconds") val sessionDurationSeconds: Int,
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("successful_requests") val successfulRequests: Int,
    @SerializedName("failed_requests") val failedRequests: Int,
    @SerializedName("invalid_samples") val invalidSamples: Int,
    @SerializedName("measured_rate_hz") val measuredRateHz: Double?,
    @SerializedName("average_latency_ms") val averageLatencyMs: Double?,
    @SerializedName("repetitions") val repetitions: List<MovementRepetitionRequest>,
    @SerializedName("movement_intelligence") val movementIntelligence: MovementIntelligenceRequest,
)

data class MovementRepetitionRequest(
    @SerializedName("rep_number") val repNumber: Int,
    @SerializedName("started_at") val startedAt: String,
    @SerializedName("ended_at") val endedAt: String,
    @SerializedName("duration_ms") val durationMs: Long,
    @SerializedName("movement_phase") val movementPhase: String?,
    val quality: String,
    val stability: String,
    val smoothness: String,
    @SerializedName("range_of_motion_signal") val rangeOfMotionSignal: String?,
    val abnormality: String?,
    val source: String,
)

data class MovementIntelligenceRequest(
    @SerializedName("exercise_recognition_status") val exerciseRecognitionStatus: String,
    @SerializedName("recognized_exercise") val recognizedExercise: String?,
    @SerializedName("prediction_source") val predictionSource: String?,
    @SerializedName("model_name") val modelName: String?,
    @SerializedName("model_version") val modelVersion: String?,
    @SerializedName("feature_schema_version") val featureSchemaVersion: String?,
    @SerializedName("prediction_timestamp") val predictionTimestamp: Long?,
    val consistency: String,
    @SerializedName("sensor_quality_status") val sensorQualityStatus: String,
    @SerializedName("baseline_status") val baselineStatus: String,
    @SerializedName("calculation_version") val calculationVersion: String,
    val anomalies: List<MovementAnomalyRequest> = emptyList(),
    val events: List<MovementEventRequest> = emptyList(),
)

data class MovementAnomalyRequest(
    @SerializedName("event_timestamp") val eventTimestamp: Long,
    @SerializedName("anomaly_type") val anomalyType: String = "UNUSUAL_MOVEMENT_PATTERN",
    val severity: String,
    @SerializedName("baseline_deviation") val baselineDeviation: Double?,
    @SerializedName("model_name") val modelName: String?,
    @SerializedName("model_version") val modelVersion: String?,
    @SerializedName("requires_review") val requiresReview: Boolean,
)

data class MovementEventRequest(
    val timestamp: Long,
    @SerializedName("event_type") val eventType: String,
    val severity: String,
    val description: String,
    val source: String,
)

data class MovementModelRecord(
    val id: String,
    @SerializedName("model_name") val modelName: String,
    val version: String,
    @SerializedName("feature_schema_version") val featureSchemaVersion: String,
    val status: String,
)

data class MovementModelsResponse(val enabled: Boolean, val models: List<MovementModelRecord>)
data class ModelArtifactResponse(val artifact: String, @SerializedName("sha256") val sha256: String)

data class SessionTransitionRequest(val status: String)
data class RegisteredDevice(
    val id: String,
    @SerializedName("device_identifier") val deviceIdentifier: String,
    @SerializedName("is_active") val isActive: Boolean = true,
)
data class DeviceResponse(val device: RegisteredDevice)
data class DevicesResponse(val devices: List<RegisteredDevice>)
data class ExerciseListResponse(val exercises: List<ExerciseRecord>)
data class ExerciseRecord(
    val id: String,
    val name: String,
    @SerializedName("default_repetitions") val defaultRepetitions: Int?,
)

interface BackendApi {
    @GET("me")
    suspend fun currentProfile(@Header("Authorization") bearer: String): BackendEnvelope<ProfileResponse>

    @GET("rehab/exercises")
    suspend fun exercises(@Header("Authorization") bearer: String): BackendEnvelope<ExerciseListResponse>

    @POST("devices")
    suspend fun registerDevice(
        @Header("Authorization") bearer: String,
        @Body request: DeviceRegistrationRequest,
    ): BackendEnvelope<DeviceResponse>

    @GET("devices")
    suspend fun devices(@Header("Authorization") bearer: String): BackendEnvelope<DevicesResponse>

    @POST("rehab/sessions")
    suspend fun createRehabSession(
        @Header("Authorization") bearer: String,
        @Body request: Map<String, Any?>,
    ): BackendEnvelope<RehabSessionResponse>

    @PATCH("rehab/sessions/{sessionId}")
    suspend fun updateRehabSession(
        @Header("Authorization") bearer: String,
        @Path("sessionId") sessionId: String,
        @Body request: SessionTransitionRequest,
    ): BackendEnvelope<RehabSessionResponse>

    @GET("rehab/sessions/{sessionId}")
    suspend fun rehabSession(
        @Header("Authorization") bearer: String,
        @Path("sessionId") sessionId: String,
    ): BackendEnvelope<RehabSessionResponse>

    @POST("rehab/sessions/{sessionId}/movement-summary")
    suspend fun uploadMovementSummary(
        @Header("Authorization") bearer: String,
        @Path("sessionId") sessionId: String,
        @Body request: MovementSummaryRequest,
    ): BackendEnvelope<Map<String, Any>>

    @GET("ml/models")
    suspend fun movementModels(
        @Header("Authorization") bearer: String,
    ): BackendEnvelope<MovementModelsResponse>

    @GET("ml/models/{modelId}/artifact")
    suspend fun movementModelArtifact(
        @Header("Authorization") bearer: String,
        @Path("modelId") modelId: String,
    ): BackendEnvelope<ModelArtifactResponse>

    @POST("wellbeing/checkins")
    suspend fun createWellbeingCheckIn(
        @Header("Authorization") bearer: String,
        @Body request: Map<String, Any?>,
    ): BackendEnvelope<Map<String, Any?>>

    @POST("wellbeing/camera/sessions")
    suspend fun createCameraWellbeingSession(
        @Header("Authorization") bearer: String,
        @Body request: Map<String, Any?>,
    ): BackendEnvelope<Map<String, Any?>>

    @POST("wellbeing/camera/sessions/{sessionId}/features")
    suspend fun createCameraWellbeingFeatures(
        @Header("Authorization") bearer: String,
        @Path("sessionId") sessionId: String,
        @Body request: Map<String, Any?>,
    ): BackendEnvelope<Map<String, Any?>>

    @POST("wellbeing/sleep")
    suspend fun createWellbeingSleep(
        @Header("Authorization") bearer: String,
        @Body request: Map<String, Any?>,
    ): BackendEnvelope<Map<String, Any?>>

    @POST("wellbeing/recovery")
    suspend fun createWellbeingRecovery(
        @Header("Authorization") bearer: String,
        @Body request: Map<String, Any?>,
    ): BackendEnvelope<Map<String, Any?>>

    @POST("wellbeing/reports")
    suspend fun createWellbeingReport(
        @Header("Authorization") bearer: String,
        @Body request: Map<String, Any?>,
    ): BackendEnvelope<Map<String, Any?>>
}

interface SupabaseAuthApi {
    @POST("token?grant_type=password")
    suspend fun signIn(
        @Header("apikey") publishableKey: String,
        @Body credentials: Map<String, String>,
    ): SupabaseSignInResponse

    @POST("token?grant_type=refresh_token")
    suspend fun refresh(
        @Header("apikey") publishableKey: String,
        @Body body: Map<String, String>,
    ): SupabaseSignInResponse
}
