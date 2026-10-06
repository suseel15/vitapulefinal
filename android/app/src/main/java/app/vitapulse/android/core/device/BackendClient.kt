package app.vitapulse.android.core.device

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import androidx.core.content.edit
import app.vitapulse.android.BuildConfig
import app.vitapulse.android.movement.data.MovementDatasetExporter
import app.vitapulse.android.movement.inference.LocalMovementModel
import app.vitapulse.android.movement.inference.ModelManager
import com.google.gson.Gson
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.UUID
import java.util.concurrent.TimeUnit

class BackendClient(context: Context) {
    private val masterKey = MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
    private val preferences = EncryptedSharedPreferences.create(
        context,
        "vitapulse-auth",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )
    private val datasetPreferences = EncryptedSharedPreferences.create(
        context,
        "vitapulse-dataset",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    private val backendApi: BackendApi? = BuildConfig.API_BASE_URL
        .takeIf { it.isNotBlank() }
        ?.let { retrofit(it).create(BackendApi::class.java) }

    private val authApi: SupabaseAuthApi? = BuildConfig.SUPABASE_URL
        .takeIf { it.isNotBlank() && BuildConfig.SUPABASE_PUBLISHABLE_KEY.isNotBlank() }
        ?.let { retrofit("${it.trimEnd('/')}/auth/v1/").create(SupabaseAuthApi::class.java) }

    suspend fun signIn(email: String, password: String): String {
        val auth = authApi ?: error("Set VITAPULSE_SUPABASE_URL and VITAPULSE_SUPABASE_PUBLISHABLE_KEY in android/local.properties.")
        val api = backendApi ?: error("Set VITAPULSE_API_BASE_URL in android/local.properties.")
        val result = auth.signIn(
            BuildConfig.SUPABASE_PUBLISHABLE_KEY,
            mapOf("email" to email, "password" to password),
        )
        val profileResponse = api.currentProfile("Bearer ${result.accessToken}")
        val profile = profileResponse.data?.profile
        check(profileResponse.success && profile?.role == "ATHLETE") {
            "This account does not have an active athlete profile."
        }
        preferences.edit {
            putString("access_token", result.accessToken)
            putString("refresh_token", result.refreshToken)
            putLong("expires_at_ms", System.currentTimeMillis() + result.expiresIn * 1_000)
            putString("athlete_id", profile.id)
        }
        return profile.displayName?.takeIf { it.isNotBlank() } ?: "Athlete"
    }

    suspend fun restoreSession(): String? {
        val token = accessToken() ?: return null
        val api = backendApi ?: error("Set VITAPULSE_API_BASE_URL in android/local.properties.")
        val result = api.currentProfile("Bearer $token")
        val profile = result.data?.profile
        check(result.success && profile?.role == "ATHLETE") {
            "The saved account does not have an active athlete profile. Sign in again."
        }
        return profile.displayName?.takeIf { it.isNotBlank() } ?: "Athlete"
    }

    suspend fun accessToken(): String? {
        val token = preferences.getString("access_token", null) ?: return null
        val expiresAt = preferences.getLong("expires_at_ms", 0)
        if (expiresAt > System.currentTimeMillis() + TOKEN_REFRESH_MARGIN_MS) return token
        val refresh = preferences.getString("refresh_token", null) ?: return null
        val auth = authApi ?: return null
        val result = auth.refresh(
            BuildConfig.SUPABASE_PUBLISHABLE_KEY,
            mapOf("refresh_token" to refresh),
        )
        preferences.edit {
            putString("access_token", result.accessToken)
            putString("refresh_token", result.refreshToken)
            putLong("expires_at_ms", System.currentTimeMillis() + result.expiresIn * 1_000)
        }
        return result.accessToken
    }

    fun currentAthleteId(): String? = preferences.getString("athlete_id", null)

    fun datasetPseudonymousAthleteId(): String {
        val athleteId = requireNotNull(currentAthleteId()) { "Sign in before exporting a training sample." }
        val salt = datasetPreferences.getString("dataset_pseudonym_salt", null) ?: UUID.randomUUID().toString().also {
            datasetPreferences.edit { putString("dataset_pseudonym_salt", it) }
        }
        return MovementDatasetExporter.pseudonym(athleteId, salt)
    }

    suspend fun syncApprovedMovementModel(modelManager: ModelManager): LocalMovementModel? {
        val api = requireNotNull(backendApi) { "Backend API is not configured." }
        val token = requireNotNull(accessToken()) { "Sign in before checking approved movement models." }
        val response = api.movementModels("******")
        check(response.success) { response.error?.message ?: "Approved movement models could not be loaded." }
        val models = response.data?.models ?: error("The backend returned no model registry response.")
        val approved = models.firstOrNull { it.status == "ACTIVE" }
        if (approved == null) {
            modelManager.clearInstalledModels()
            return null
        }
        if (approved.version == modelManager.installedVersion()) {
            return modelManager.loadActiveModel()
        }
        val artifactResponse = api.movementModelArtifact("******", approved.id)
        check(artifactResponse.success) {
            artifactResponse.error?.message ?: "The approved movement model could not be downloaded."
        }
        val artifact = requireNotNull(artifactResponse.data) { "The backend returned no movement model artifact." }
        return modelManager.installApprovedModel(
            artifact.artifact.toByteArray(Charsets.UTF_8),
            artifact.sha256,
        )
    }

    suspend fun registerDevice(device: Esp32Device): RegisteredDevice {
        val api = requireNotNull(backendApi) { "Backend API is not configured." }
        val token = requireNotNull(accessToken()) { "Sign in again before syncing the device." }
        val result = api.registerDevice(
            "Bearer $token",
            DeviceRegistrationRequest(
                deviceIdentifier = device.identifier,
                ip = device.ipAddress,
                sensorType = device.sensorType,
                transport = device.transport,
                firmwareProtocol = device.firmwareProtocol,
            ),
        )
        check(result.success) { result.error?.message ?: "Device registration failed." }
        return requireNotNull(result.data?.device) { "The backend returned no registered device." }
    }

    suspend fun registeredDeviceId(identifier: String): String? {
        val api = requireNotNull(backendApi) { "Backend API is not configured." }
        val token = requireNotNull(accessToken()) { "Sign in before loading registered devices." }
        val result = api.devices("Bearer $token")
        check(result.success) { result.error?.message ?: "Registered devices could not be loaded." }
        return result.data?.devices?.firstOrNull { it.deviceIdentifier == identifier && it.isActive }?.id
    }

    suspend fun exercises(): List<ExerciseRecord> {
        val api = requireNotNull(backendApi) { "Backend API is not configured." }
        val token = requireNotNull(accessToken()) { "Sign in before loading assigned exercises." }
        val result = api.exercises("Bearer $token")
        check(result.success) { result.error?.message ?: "Exercises could not be loaded." }
        return requireNotNull(result.data?.exercises) { "The backend returned no exercise list." }
    }

    suspend fun createLiveSession(
        clientSessionId: String,
        exerciseId: String,
        deviceId: String,
        placement: String,
        repetitions: Int,
    ): BackendMovementSession {
        val api = requireNotNull(backendApi) { "Backend API is not configured." }
        val token = requireNotNull(accessToken()) { "Sign in again before syncing." }
        val result = api.createRehabSession(
            "Bearer $token",
            mapOf(
                "exercise_id" to exerciseId,
                "client_session_id" to clientSessionId,
                "source" to "LIVE_SENSOR",
                "sensor_type" to "MPU6050",
                "sensor_placement" to placement,
                "device_id" to deviceId,
                "target_repetitions" to repetitions,
            ),
        )
        check(result.success) { result.error?.message ?: "Could not create a live sensor session." }
        return requireNotNull(result.data?.session) { "The backend returned no session record." }
    }

    suspend fun transitionSession(sessionId: String, status: String) {
        val api = requireNotNull(backendApi)
        val token = requireNotNull(accessToken())
        val result = api.updateRehabSession("Bearer $token", sessionId, SessionTransitionRequest(status))
        check(result.success) { result.error?.message ?: "Session state could not be synchronized." }
    }

    suspend fun sessionStatus(sessionId: String): String {
        val api = requireNotNull(backendApi)
        val token = requireNotNull(accessToken())
        val result = api.rehabSession("Bearer $token", sessionId)
        check(result.success) { result.error?.message ?: "Session state could not be loaded." }
        return requireNotNull(result.data?.session?.status) { "The backend returned no session state." }
    }

    suspend fun uploadMovementSummary(sessionId: String, summary: MovementSummaryRequest) {
        val api = requireNotNull(backendApi)
        val token = requireNotNull(accessToken())
        val result = api.uploadMovementSummary("Bearer $token", sessionId, summary)
        check(result.success) { result.error?.message ?: "Session summary could not be synchronized." }
    }

    suspend fun syncWellbeingCheckIn(payload: Map<String, Any?>) {
        val (api, bearer) = authenticatedBackend()
        val result = api.createWellbeingCheckIn(bearer, payload)
        check(result.success) { result.error?.message ?: "The wellbeing check-in could not be synchronized." }
    }

    suspend fun syncCameraWellbeingSession(sessionPayload: Map<String, Any?>, featurePayload: Map<String, Any?>) {
        val (api, bearer) = authenticatedBackend()
        val session = api.createCameraWellbeingSession(bearer, sessionPayload)
        check(session.success) { session.error?.message ?: "The camera assessment could not be synchronized." }
        val sessionId = sessionPayload["id"]?.toString()
            ?: error("The camera assessment has no stable session identifier.")
        val features = api.createCameraWellbeingFeatures(bearer, sessionId, featurePayload)
        check(features.success) { features.error?.message ?: "The camera observations could not be synchronized." }
    }

    suspend fun syncWellbeingSleep(payload: Map<String, Any?>) {
        val (api, bearer) = authenticatedBackend()
        val result = api.createWellbeingSleep(bearer, payload)
        check(result.success) { result.error?.message ?: "The sleep record could not be synchronized." }
    }

    suspend fun syncWellbeingRecovery(payload: Map<String, Any?>) {
        val (api, bearer) = authenticatedBackend()
        val result = api.createWellbeingRecovery(bearer, payload)
        check(result.success) { result.error?.message ?: "The recovery record could not be synchronized." }
    }

    suspend fun syncWellbeingReport(payload: Map<String, Any?>) {
        val (api, bearer) = authenticatedBackend()
        val result = api.createWellbeingReport(bearer, payload)
        check(result.success) { result.error?.message ?: "The wellbeing report could not be synchronized." }
    }

    private suspend fun authenticatedBackend(): Pair<BackendApi, String> {
        val api = requireNotNull(backendApi) { "Backend API is not configured." }
        val token = requireNotNull(accessToken()) { "Sign in before synchronizing wellbeing data." }
        return api to "Bearer $token"
    }

    fun signOut() {
        preferences.edit { clear() }
    }

    private fun retrofit(baseUrl: String): Retrofit = Retrofit.Builder()
        .baseUrl(if (baseUrl.endsWith('/')) baseUrl else "$baseUrl/")
        .client(okhttp3.OkHttpClient.Builder()
            .connectTimeout(8, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .build())
        .addConverterFactory(GsonConverterFactory.create(Gson()))
        .build()

    companion object {
        private const val TOKEN_REFRESH_MARGIN_MS = 60_000L
    }
}
