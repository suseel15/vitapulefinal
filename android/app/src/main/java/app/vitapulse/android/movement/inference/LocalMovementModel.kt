package app.vitapulse.android.movement.inference

import android.content.Context
import app.vitapulse.android.movement.domain.SensorQualityStatus
import app.vitapulse.android.movement.features.FEATURE_SCHEMA_VERSION
import app.vitapulse.android.movement.features.MOVEMENT_FEATURE_NAMES
import app.vitapulse.android.movement.features.MovementFeatures
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.io.File
import java.security.MessageDigest

enum class ExerciseType {
    REST, WALK, SQUAT, SIT_TO_STAND, LEG_RAISE, CALF_RAISE, HAMSTRING_BRIDGE, BALANCE, UNKNOWN
}

enum class PredictionSource { MODEL_INFERRED, DETERMINISTIC, MANUAL }

data class ModelPrediction(
    val exercise: ExerciseType,
    val timestampMs: Long,
    val source: PredictionSource,
    val modelName: String,
    val modelVersion: String,
    internal val voteShare: Double,
)

interface LocalMovementModel {
    val modelName: String
    val modelVersion: String
    val featureSchemaVersion: String
    val supportedExercises: Set<ExerciseType>
    val supportedSensorPlacements: Set<String>
    val minimumSamplingRateHz: Double

    fun predict(
        features: MovementFeatures,
        sensorPlacement: String,
        quality: SensorQualityStatus,
        timestampMs: Long,
    ): ModelPrediction?
}

class RandomForestLocalModel private constructor(
    private val artifact: JsonObject,
) : LocalMovementModel {
    override val modelName = artifact.get("model_name").asString
    override val modelVersion = artifact.get("model_version").asString
    override val featureSchemaVersion = artifact.get("feature_schema_version").asString
    override val supportedExercises: Set<ExerciseType> = artifact.getAsJsonArray("classes")
        .map { value -> ExerciseType.valueOf(value.asString) }
        .toSet()
    override val supportedSensorPlacements: Set<String> = artifact.getAsJsonArray("supported_sensor_placements")
        .map { it.asString }
        .toSet()
    override val minimumSamplingRateHz = artifact.get("minimum_sampling_rate_hz").asDouble
    private val featureNames = artifact.getAsJsonArray("feature_names").map { it.asString }

    override fun predict(
        features: MovementFeatures,
        sensorPlacement: String,
        quality: SensorQualityStatus,
        timestampMs: Long,
    ): ModelPrediction? {
        if (featureSchemaVersion != FEATURE_SCHEMA_VERSION ||
            features.names != featureNames ||
            features.names != MOVEMENT_FEATURE_NAMES ||
            features.samplingRateHz < minimumSamplingRateHz ||
            sensorPlacement !in supportedSensorPlacements ||
            quality !in setOf(SensorQualityStatus.EXCELLENT, SensorQualityStatus.GOOD)
        ) return null

        val votes = mutableMapOf<ExerciseType, Int>()
        artifact.getAsJsonArray("trees").forEach { tree ->
            val label = ExerciseType.valueOf(walk(tree.asJsonObject, features.values))
            votes[label] = (votes[label] ?: 0) + 1
        }
        val winner = votes.entries.sortedWith(compareByDescending<Map.Entry<ExerciseType, Int>> { it.value }
            .thenBy { it.key.name }).firstOrNull() ?: return null
        return ModelPrediction(
            exercise = winner.key,
            timestampMs = timestampMs,
            source = PredictionSource.MODEL_INFERRED,
            modelName = modelName,
            modelVersion = modelVersion,
            voteShare = winner.value.toDouble() / artifact.getAsJsonArray("trees").size(),
        )
    }

    private fun walk(root: JsonObject, values: FloatArray): String {
        var node = root
        while (!node.has("class")) {
            val featureIndex = node.get("feature_index").asInt
            require(featureIndex in values.indices) { "Model tree references an invalid feature index." }
            node = if (values[featureIndex] <= node.get("threshold").asFloat) {
                node.getAsJsonObject("left")
            } else {
                node.getAsJsonObject("right")
            }
        }
        return node.get("class").asString
    }

    companion object {
        fun fromVerifiedArtifact(bytes: ByteArray, expectedSha256: String): RandomForestLocalModel {
            val digest = MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            require(digest.equals(expectedSha256, ignoreCase = true)) { "Model checksum verification failed." }
            val json = JsonParser.parseString(bytes.toString(Charsets.UTF_8)).asJsonObject
            require(json.get("format")?.asString == "vitapulse-random-forest-json-v1") {
                "Unsupported movement model format."
            }
            require(json.get("status")?.asString == "ACTIVE") { "Only an approved ACTIVE model can be installed." }
            require(json.get("feature_schema_version")?.asString == FEATURE_SCHEMA_VERSION) {
                "Model feature schema is incompatible with this app."
            }
            require(json.getAsJsonArray("feature_names")?.map { it.asString } == MOVEMENT_FEATURE_NAMES) {
                "Model feature ordering is incompatible with this app."
            }
            require((json.getAsJsonArray("trees")?.size() ?: 0) > 0) { "Model artifact has no trees." }
            require(json.get("model_name")?.asString?.isNotBlank() == true) { "Model artifact has no model name." }
            require(json.get("model_version")?.asString?.isNotBlank() == true) { "Model artifact has no model version." }
            val minimumRate = json.get("minimum_sampling_rate_hz")?.asDouble
            require(minimumRate != null && minimumRate.isFinite() && minimumRate in 0.0..100.0) {
                "Model artifact has an invalid sampling-rate requirement."
            }
            val placements = json.getAsJsonArray("supported_sensor_placements")
            require(
                placements != null && placements.size() > 0 &&
                    placements.all { it.asString in setOf("THIGH", "SHANK", "FOREARM", "UPPER_ARM", "WAIST", "CHEST", "OTHER") },
            ) { "Model artifact has no supported sensor placements." }
            val classes = json.getAsJsonArray("classes")
            require(classes != null && classes.size() > 0) { "Model artifact has no supported exercise classes." }
            classes.forEach { ExerciseType.valueOf(it.asString) }
            return RandomForestLocalModel(json)
        }
    }
}

class ModelManager(context: Context) {
    private val directory = File(context.filesDir, "movement-models").apply { mkdirs() }
    private val activeFile = File(directory, "active.json")
    private val previousFile = File(directory, "previous.json")
    private val activeChecksumFile = File(directory, "active.sha256")
    private val previousChecksumFile = File(directory, "previous.sha256")

    fun hasInstalledModel(): Boolean = activeFile.isFile

    fun installedVersion(): String? = if (!activeFile.isFile) null else {
        JsonParser.parseString(activeFile.readText()).asJsonObject.get("model_version")?.asString
    }

    fun clearInstalledModels() {
        listOf(activeFile, activeChecksumFile, previousFile, previousChecksumFile).forEach { file ->
            if (file.exists()) check(file.delete()) { "Could not remove a model that is no longer approved." }
        }
    }

    fun installApprovedModel(bytes: ByteArray, sha256: String): LocalMovementModel {
        val model = RandomForestLocalModel.fromVerifiedArtifact(bytes, sha256)
        val candidate = File(directory, "candidate.json")
        val candidateChecksum = File(directory, "candidate.sha256")
        candidate.writeBytes(bytes)
        candidateChecksum.writeText(sha256.lowercase())
        if (activeFile.exists()) {
            if (previousFile.exists()) check(previousFile.delete()) { "Could not replace previous model backup." }
            if (previousChecksumFile.exists()) check(previousChecksumFile.delete()) { "Could not replace previous checksum backup." }
            check(activeFile.renameTo(previousFile)) { "Could not preserve the current model for rollback." }
            if (activeChecksumFile.exists()) {
                check(activeChecksumFile.renameTo(previousChecksumFile)) { "Could not preserve the model checksum for rollback." }
            }
        }
        if (!candidate.renameTo(activeFile)) {
            if (previousFile.exists()) {
                previousFile.renameTo(activeFile)
                previousChecksumFile.takeIf { it.exists() }?.renameTo(activeChecksumFile)
            }
            error("Could not activate the verified movement model.")
        }
        check(candidateChecksum.renameTo(activeChecksumFile)) { "Could not persist the model checksum." }
        return model
    }

    fun loadActiveModel(): LocalMovementModel? {
        if (!activeFile.isFile) return null
        val bytes = activeFile.readBytes()
        val checksum = activeChecksumFile.takeIf { it.isFile }?.readText()?.trim()
            ?: error("The installed movement model has no registry checksum.")
        return RandomForestLocalModel.fromVerifiedArtifact(bytes, checksum)
    }

    fun rollback(): Boolean {
        if (!previousFile.isFile) return false
        val previousBytes = previousFile.readBytes()
        val checksum = previousChecksumFile.takeIf { it.isFile }?.readText()?.trim()
            ?: error("The rollback artifact has no registry checksum.")
        RandomForestLocalModel.fromVerifiedArtifact(previousBytes, checksum)
        val discarded = File(directory, "discarded.json")
        val discardedChecksum = File(directory, "discarded.sha256")
        if (activeFile.exists()) check(activeFile.renameTo(discarded)) { "Could not preserve current model before rollback." }
        if (activeChecksumFile.exists()) check(activeChecksumFile.renameTo(discardedChecksum)) { "Could not preserve current checksum before rollback." }
        check(previousFile.renameTo(activeFile)) { "Could not restore the previous model." }
        check(previousChecksumFile.renameTo(activeChecksumFile)) { "Could not restore previous model checksum." }
        if (discarded.exists()) check(discarded.delete()) { "Could not clean the superseded model." }
        if (discardedChecksum.exists()) check(discardedChecksum.delete()) { "Could not clean the superseded checksum." }
        return true
    }
}
