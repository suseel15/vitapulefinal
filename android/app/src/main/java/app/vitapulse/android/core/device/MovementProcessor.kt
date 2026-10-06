package app.vitapulse.android.core.device

import app.vitapulse.android.movement.domain.SensorQualityMetrics
import app.vitapulse.android.movement.domain.SensorQualityMonitor
import app.vitapulse.android.movement.domain.SensorQualityStatus
import app.vitapulse.android.movement.features.MovementFeatureExtractor
import app.vitapulse.android.movement.inference.ExerciseType
import app.vitapulse.android.movement.inference.LocalMovementModel
import app.vitapulse.android.movement.inference.ModelPrediction
import app.vitapulse.android.movement.processing.MovementWindowBuilder
import app.vitapulse.android.movement.processing.SignalProcessor
import app.vitapulse.android.movement.session.ExerciseRepetitionDetector
import app.vitapulse.android.movement.session.MovementRepetition
import app.vitapulse.android.movement.session.RepeatedAnomalyEngine
import app.vitapulse.android.movement.session.fatigueSignal
import app.vitapulse.android.movement.session.movementConsistency
import app.vitapulse.android.movement.session.movementQuality
import app.vitapulse.android.movement.session.repetitionProfile
import app.vitapulse.android.movement.session.MovementRiskSignal
import app.vitapulse.android.movement.session.MovementRiskSignalProvider
import kotlin.math.sqrt
import kotlin.math.abs
import kotlin.math.max

data class MovementAnalysis(
    val movementQuality: String,
    val stability: String,
    val smoothness: String,
    val fatigueSignal: String,
    val repetitionCount: Int,
    val consistency: String = "INSUFFICIENT_DATA",
    val sensorQuality: String = "INSUFFICIENT",
    val recognition: String = "MODEL_UNAVAILABLE",
    val recognizedExercise: String? = null,
    val modelVersion: String? = null,
)

class MovementProcessor(
    private val signalProcessor: SignalProcessor = SignalProcessor(),
    private val qualityMonitor: SensorQualityMonitor = SensorQualityMonitor(),
    private val windowBuilder: MovementWindowBuilder = MovementWindowBuilder(),
    private val featureExtractor: MovementFeatureExtractor = MovementFeatureExtractor(),
) : MovementRiskSignalProvider {
    private val rawWindow = ArrayDeque<MovementSample>()
    private val repetitions = mutableListOf<MovementRepetition>()
    private val anomalyEngine = RepeatedAnomalyEngine()
    private var repetitionDetector: ExerciseRepetitionDetector? = null
    private var model: LocalMovementModel? = null
    private var placement = "OTHER"
    private var exerciseId: String? = null
    private var invalidSamples = 0
    var repetitionCount: Int = 0
        private set
    var completedRepetitions: List<MovementRepetition> = emptyList()
        private set
    var latestPrediction: ModelPrediction? = null
        private set
    var latestAnomalyDetected: Boolean = false
        private set
    private var lastQuality = SensorQualityMetrics(SensorQualityStatus.INSUFFICIENT, 0, null, null, null, 0, 0)

    fun configureExercise(exerciseName: String, sensorPlacement: String) {
        reset()
        placement = sensorPlacement
        exerciseId = repetitionProfile(exerciseName)?.exercise?.name
        repetitionDetector = repetitionProfile(exerciseName)?.let(::ExerciseRepetitionDetector)
    }

    fun setLocalModel(localModel: LocalMovementModel?) {
        model = localModel
    }

    fun add(sample: MovementSample, calibration: SessionCalibration?): MovementAnalysis {
        val processed = signalProcessor.process(sample, calibration)
        if (processed == null) {
            invalidSamples += 1
            return summarize()
        }
        rawWindow.addLast(sample)
        while (rawWindow.size > MAX_QUALITY_WINDOW) rawWindow.removeFirst()
        lastQuality = qualityMonitor.assess(rawWindow.toList(), invalidSamples = invalidSamples)
        repetitionDetector?.feed(processed)?.let { repetition ->
            val prior = repetitions.takeLast(5)
            val durationMean = prior.map { it.durationMs.toDouble() }.average()
            val durationStd = if (prior.size >= 3) {
                sqrt(prior.sumOf { (it.durationMs - durationMean) * (it.durationMs - durationMean) } / prior.size)
            } else {
                0.0
            }
            val amplitudeMean = prior.map { it.amplitude }.average()
            val amplitudeStd = if (prior.size >= 3) {
                sqrt(prior.sumOf { (it.amplitude - amplitudeMean) * (it.amplitude - amplitudeMean) } / prior.size)
            } else {
                0.0
            }
            repetitions += repetition
            repetitionCount = repetitions.size
            completedRepetitions = repetitions.toList()
            val durationDeviation = if (prior.size >= 3) {
                abs(repetition.durationMs - durationMean) / max(durationStd, durationMean * 0.1)
            } else {
                0.0
            }
            val amplitudeDeviation = if (prior.size >= 3) {
                abs(repetition.amplitude - amplitudeMean) / max(amplitudeStd, abs(amplitudeMean) * 0.1)
            } else {
                0.0
            }
            latestAnomalyDetected = anomalyEngine.observe(repetition, durationDeviation, amplitudeDeviation)
        }
        windowBuilder.add(sample)?.let { window ->
            val features = featureExtractor.extract(window.samples) ?: return@let
            latestPrediction = model?.predict(
                features = features,
                sensorPlacement = placement,
                quality = lastQuality.status,
                timestampMs = sample.appTimestamp,
            )
        }
        return summarize()
    }

    fun reset() {
        repetitionDetector?.reset()
        signalProcessor.reset()
        windowBuilder.reset()
        rawWindow.clear()
        repetitions.clear()
        anomalyEngine.reset()
        invalidSamples = 0
        repetitionCount = 0
        completedRepetitions = emptyList()
        latestPrediction = null
        latestAnomalyDetected = false
        exerciseId = null
        lastQuality = SensorQualityMetrics(SensorQualityStatus.INSUFFICIENT, 0, null, null, null, 0, 0)
    }

    fun summarize(): MovementAnalysis {
        val samples = rawWindow.toList()
        if (samples.size < MINIMUM_QUALITY_SAMPLES ||
            lastQuality.status == SensorQualityStatus.INSUFFICIENT
        ) {
            return insufficient(repetitions.size, lastQuality.status.name)
        }
        val magnitudes = samples.map { it.accelerationMagnitude }
        val mean = magnitudes.average()
        val deviation = sqrt(magnitudes.sumOf { (it - mean) * (it - mean) } / magnitudes.size)
        val jerk = magnitudes.zipWithNext().map { (left, right) -> kotlin.math.abs(right - left) }.average()
        val stability = quality(deviation, good = 0.08, moderate = 0.20)
        val smoothness = quality(jerk, good = 0.04, moderate = 0.12)
        val movementQuality = if (repetitions.size < 3) {
            "INSUFFICIENT_DATA"
        } else {
            movementQuality(repetitions, lastQuality)
        }
        val predicted = latestPrediction
        val recognition = when {
            predicted?.exercise == ExerciseType.UNKNOWN -> "UNKNOWN"
            predicted != null -> "RECOGNIZED"
            model == null -> "MODEL_UNAVAILABLE"
            lastQuality.status !in setOf(SensorQualityStatus.EXCELLENT, SensorQualityStatus.GOOD) -> "INSUFFICIENT_DATA"
            else -> "UNKNOWN"
        }
        return MovementAnalysis(
            movementQuality = movementQuality,
            stability = stability,
            smoothness = smoothness,
            fatigueSignal = fatigueSignal(repetitions).name,
            repetitionCount = repetitions.size,
            consistency = movementConsistency(repetitions),
            sensorQuality = lastQuality.status.name,
            recognition = recognition,
            recognizedExercise = predicted?.exercise?.name?.takeUnless { it == ExerciseType.UNKNOWN.name },
            modelVersion = predicted?.modelVersion,
        )
    }

    override fun latestSignals(): List<MovementRiskSignal> = anomalyEngine.latestSignals()

    private fun insufficient(repetitions: Int, qualityStatus: String) = MovementAnalysis(
        "INSUFFICIENT_DATA",
        "INSUFFICIENT_DATA",
        "INSUFFICIENT_DATA",
        fatigueSignal(repetitions = emptyList()).name,
        repetitions,
        sensorQuality = qualityStatus,
    )

    private fun quality(value: Double, good: Double, moderate: Double): String = when {
        !value.isFinite() -> "INSUFFICIENT_DATA"
        value <= good -> "GOOD"
        value <= moderate -> "MODERATE"
        else -> "NEEDS_ATTENTION"
    }

    companion object {
        private const val MINIMUM_QUALITY_SAMPLES = 10
        private const val MAX_QUALITY_WINDOW = 300
    }
}
