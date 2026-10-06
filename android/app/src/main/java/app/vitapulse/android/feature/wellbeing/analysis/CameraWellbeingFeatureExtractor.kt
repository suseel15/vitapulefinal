package app.vitapulse.android.feature.wellbeing.analysis

import kotlin.math.abs
import kotlin.math.pow
import kotlin.math.sqrt

data class FrameObservation(
    val timestampMs: Long,
    val faceCount: Int,
    val centerX: Double? = null,
    val centerY: Double? = null,
    val widthFraction: Double? = null,
    val headEulerX: Double? = null,
    val headEulerY: Double? = null,
    val headEulerZ: Double? = null,
    val leftEyeOpenProbability: Double? = null,
    val rightEyeOpenProbability: Double? = null,
    val smileProbability: Double? = null,
    val averageLuma: Double? = null,
    val sharpness: Double? = null,
)

enum class FacePrecheck {
    READY,
    NO_FACE,
    MULTIPLE_FACES,
    FACE_TOO_SMALL,
    FACE_OFF_CENTER,
    POOR_LIGHTING,
    BLURRY,
    FACE_NOT_FACING_CAMERA,
}

data class CameraWellbeingFeatures(
    val facePresenceRatio: Double,
    val validFrameRatio: Double,
    val facePositionStability: String,
    val headMovementMagnitude: Double?,
    val headMovementVariability: Double?,
    val headOrientationRange: Double?,
    val eyeObservationRatio: Double?,
    val smileObservationRatio: Double?,
    val captureQuality: String,
    val faceDetectedFrames: Int,
    val validFrames: Int,
    val invalidFrames: Int,
    val multipleFaceFrames: Int,
    val poorLightingFrames: Int,
    val faceOutOfFrameFrames: Int,
    val durationSeconds: Int,
)

object CameraWellbeingFeatureExtractor {
    const val FEATURE_SCHEMA_VERSION = "camera-wellbeing-v1"

    fun precheck(observation: FrameObservation): FacePrecheck {
        if (observation.faceCount == 0) return FacePrecheck.NO_FACE
        if (observation.faceCount > 1) return FacePrecheck.MULTIPLE_FACES
        if ((observation.widthFraction ?: 0.0) < MINIMUM_FACE_WIDTH) return FacePrecheck.FACE_TOO_SMALL
        val x = observation.centerX ?: return FacePrecheck.NO_FACE
        val y = observation.centerY ?: return FacePrecheck.NO_FACE
        if (abs(x - 0.5) > MAXIMUM_CENTER_OFFSET || abs(y - 0.5) > MAXIMUM_CENTER_OFFSET) {
            return FacePrecheck.FACE_OFF_CENTER
        }
        if (listOfNotNull(observation.headEulerX, observation.headEulerY).any { abs(it) > MAXIMUM_HEAD_ANGLE } ||
            (observation.headEulerZ?.let { abs(it) > MAXIMUM_ROLL_ANGLE } == true)
        ) return FacePrecheck.FACE_NOT_FACING_CAMERA
        if ((observation.averageLuma ?: 0.0) !in MINIMUM_LUMA..MAXIMUM_LUMA) {
            return FacePrecheck.POOR_LIGHTING
        }
        if (observation.sharpness != null && observation.sharpness < MINIMUM_SHARPNESS) return FacePrecheck.BLURRY
        return FacePrecheck.READY
    }

    fun extract(observations: List<FrameObservation>, durationSeconds: Int = 30): CameraWellbeingFeatures {
        require(observations.isNotEmpty()) { "No camera observations were recorded." }
        require(durationSeconds in 0..30) { "Camera session duration must be between zero and 30 seconds." }

        val valid = observations.filter { precheck(it) == FacePrecheck.READY }
        val present = observations.count { it.faceCount == 1 }
        val multiple = observations.count { it.faceCount > 1 }
        val poorLighting = observations.count {
            it.faceCount == 1 && (it.averageLuma ?: 0.0) !in MINIMUM_LUMA..MAXIMUM_LUMA
        }
        val outOfFrame = observations.count {
            it.faceCount == 1 &&
                (it.centerX == null || it.centerY == null ||
                    abs(it.centerX - 0.5) > MAXIMUM_CENTER_OFFSET ||
                    abs(it.centerY - 0.5) > MAXIMUM_CENTER_OFFSET)
        }
        val positions = valid.mapNotNull { observation ->
            val x = observation.centerX ?: return@mapNotNull null
            val y = observation.centerY ?: return@mapNotNull null
            x to y
        }
        val movementSteps = positions.zipWithNext().map { (previous, current) ->
            sqrt((current.first - previous.first).pow(2) + (current.second - previous.second).pow(2))
        }
        val orientationRanges = listOf(
            valid.mapNotNull { it.headEulerX }.rangeOrNull(),
            valid.mapNotNull { it.headEulerY }.rangeOrNull(),
            valid.mapNotNull { it.headEulerZ }.rangeOrNull(),
        ).filterNotNull()
        val eyeValues = valid.flatMap { observation ->
            listOfNotNull(observation.leftEyeOpenProbability, observation.rightEyeOpenProbability)
        }
        val smileValues = valid.mapNotNull { it.smileProbability }
        val validRatio = valid.size.toDouble() / observations.size
        val quality = when {
            validRatio >= 0.8 -> "GOOD"
            validRatio >= 0.5 -> "FAIR"
            valid.isNotEmpty() -> "POOR"
            else -> "INSUFFICIENT_DATA"
        }
        return CameraWellbeingFeatures(
            facePresenceRatio = present.toDouble() / observations.size,
            validFrameRatio = validRatio,
            facePositionStability = when {
                positions.size < 3 -> "INSUFFICIENT_DATA"
                (movementSteps.averageOrNull() ?: 0.0) <= 0.025 -> "STABLE"
                else -> "VARIABLE"
            },
            headMovementMagnitude = movementSteps.averageOrNull(),
            headMovementVariability = movementSteps.standardDeviationOrNull(),
            headOrientationRange = orientationRanges.averageOrNull(),
            eyeObservationRatio = eyeValues.takeIf { it.isNotEmpty() }
                ?.let { eyeValues.size.toDouble() / (valid.size * 2).coerceAtLeast(1) },
            smileObservationRatio = smileValues.takeIf { it.isNotEmpty() }
                ?.let { smileValues.size.toDouble() / valid.size.coerceAtLeast(1) },
            captureQuality = quality,
            faceDetectedFrames = present,
            validFrames = valid.size,
            invalidFrames = observations.size - valid.size,
            multipleFaceFrames = multiple,
            poorLightingFrames = poorLighting,
            faceOutOfFrameFrames = outOfFrame,
            durationSeconds = durationSeconds,
        )
    }

    private fun List<Double>.averageOrNull(): Double? = takeIf { isNotEmpty() }?.average()

    private fun List<Double>.standardDeviationOrNull(): Double? {
        if (isEmpty()) return null
        val average = average()
        return sqrt(map { (it - average).pow(2) }.average())
    }

    private fun List<Double>.rangeOrNull(): Double? = takeIf { isNotEmpty() }?.let { max() - min() }

    private const val MINIMUM_FACE_WIDTH = 0.2
    private const val MAXIMUM_CENTER_OFFSET = 0.22
    private const val MINIMUM_LUMA = 30.0
    private const val MAXIMUM_LUMA = 235.0
    private const val MINIMUM_SHARPNESS = 3.0
    private const val MAXIMUM_HEAD_ANGLE = 25.0
    private const val MAXIMUM_ROLL_ANGLE = 20.0
}
