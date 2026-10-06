package app.vitapulse.android.movement.session

import app.vitapulse.android.movement.domain.SensorQualityMetrics
import app.vitapulse.android.movement.domain.SensorQualityStatus
import app.vitapulse.android.movement.inference.ExerciseType
import app.vitapulse.android.movement.processing.ProcessedMovementSample
import kotlin.math.abs
import kotlin.math.sqrt

enum class RepetitionQuality { GOOD, MODERATE, NEEDS_ATTENTION, INSUFFICIENT_DATA }

data class ExerciseRepProfile(
    val exercise: ExerciseType,
    val onsetThreshold: Double,
    val restThreshold: Double,
    val minimumDurationMs: Long,
    val maximumDurationMs: Long,
    val refractoryMs: Long = 400,
) {
    init {
        require(onsetThreshold > restThreshold && restThreshold >= 0)
        require(minimumDurationMs > 0 && maximumDurationMs > minimumDurationMs)
    }
}

data class MovementRepetition(
    val number: Int,
    val startedAtMs: Long,
    val endedAtMs: Long,
    val durationMs: Long,
    val quality: RepetitionQuality,
    val amplitude: Double,
    val smoothness: Double,
    val source: String = "LIVE_SENSOR",
)

data class MovementRiskSignal(
    val movementRiskSignal: String,
    val source: String,
    val severity: String,
    val timestampMs: Long,
    val evidence: Map<String, String>,
)

fun interface MovementRiskSignalProvider {
    fun latestSignals(): List<MovementRiskSignal>
}

class ExerciseRepetitionDetector(profile: ExerciseRepProfile) {
    private val config = profile
    private var activeStart: Long? = null
    private var lastEndedAt: Long = Long.MIN_VALUE
    private var peakAmplitude = 0.0
    private var variation = 0.0
    private var previous = 0.0
    private var samples = 0
    private val durations = mutableListOf<Long>()
    private var number = 0

    fun feed(sample: ProcessedMovementSample): MovementRepetition? {
        val value = sample.dynamicAccelerationMagnitude
        if (!value.isFinite()) return null
        val active = activeStart
        if (active == null) {
            if (value >= config.onsetThreshold && sample.raw.appTimestamp - lastEndedAt >= config.refractoryMs) {
                activeStart = sample.raw.appTimestamp
                peakAmplitude = value
                variation = 0.0
                previous = value
                samples = 1
            }
            return null
        }
        peakAmplitude = maxOf(peakAmplitude, value)
        variation += abs(value - previous)
        previous = value
        samples += 1
        val duration = sample.raw.appTimestamp - active
        if (duration > config.maximumDurationMs) {
            activeStart = null
            lastEndedAt = sample.raw.appTimestamp
            return null
        }
        if (value > config.restThreshold) return null
        activeStart = null
        lastEndedAt = sample.raw.appTimestamp
        if (duration < config.minimumDurationMs || samples < 4) return null
        number += 1
        durations += duration
        val amplitudeHistory = durations.size
        val durationVariation = if (durations.size >= 3) coefficientOfVariation(durations.takeLast(5).map(Long::toDouble)) else null
        val normalizedSmoothness = variation / samples.coerceAtLeast(1)
        val quality = when {
            durationVariation == null -> RepetitionQuality.INSUFFICIENT_DATA
            durationVariation >= 0.35 || normalizedSmoothness >= 0.22 -> RepetitionQuality.NEEDS_ATTENTION
            durationVariation >= 0.20 || normalizedSmoothness >= 0.12 -> RepetitionQuality.MODERATE
            else -> RepetitionQuality.GOOD
        }
        return MovementRepetition(number, active, sample.raw.appTimestamp, duration, quality, peakAmplitude, normalizedSmoothness)
    }

    fun reset() {
        activeStart = null
        lastEndedAt = Long.MIN_VALUE
        peakAmplitude = 0.0
        variation = 0.0
        previous = 0.0
        samples = 0
        durations.clear()
        number = 0
    }

    private fun coefficientOfVariation(values: List<Double>): Double {
        val mean = values.average()
        return if (mean <= 0) Double.POSITIVE_INFINITY
        else sqrt(values.sumOf { (it - mean) * (it - mean) } / values.size) / mean
    }
}

fun repetitionProfile(exerciseName: String): ExerciseRepProfile? {
    val name = exerciseName.lowercase().replace('-', ' ').replace('_', ' ')
    return when {
        "squat" in name -> ExerciseRepProfile(ExerciseType.SQUAT, 0.22, 0.09, 700, 12_000)
        "calf raise" in name -> ExerciseRepProfile(ExerciseType.CALF_RAISE, 0.14, 0.06, 450, 8_000)
        "sit to stand" in name -> ExerciseRepProfile(ExerciseType.SIT_TO_STAND, 0.20, 0.08, 700, 10_000)
        "bridge" in name -> ExerciseRepProfile(ExerciseType.HAMSTRING_BRIDGE, 0.16, 0.07, 700, 12_000)
        "leg raise" in name -> ExerciseRepProfile(ExerciseType.LEG_RAISE, 0.16, 0.07, 500, 10_000)
        else -> null
    }
}

enum class FatigueSignal { LOW, MODERATE, HIGH, INSUFFICIENT_DATA }

fun fatigueSignal(repetitions: List<MovementRepetition>): FatigueSignal {
    if (repetitions.size < 6) return FatigueSignal.INSUFFICIENT_DATA
    val midpoint = repetitions.size / 2
    val first = repetitions.take(midpoint).map { it.durationMs }.average()
    val last = repetitions.drop(midpoint).map { it.durationMs }.average()
    if (first <= 0 || !first.isFinite() || !last.isFinite()) return FatigueSignal.INSUFFICIENT_DATA
    val durationIncrease = (last - first) / first
    val attentionCount = repetitions.drop(midpoint).count { it.quality == RepetitionQuality.NEEDS_ATTENTION }
    return when {
        durationIncrease >= 0.35 || attentionCount >= maxOf(2, repetitions.size / 4) -> FatigueSignal.HIGH
        durationIncrease >= 0.15 || attentionCount > 0 -> FatigueSignal.MODERATE
        else -> FatigueSignal.LOW
    }
}

data class PersonalMovementBaseline(
    val exerciseId: String,
    val sensorPlacement: String,
    val sessionCount: Int,
    val repetitionCount: Int,
    val meanDurationMs: Double,
    val durationStandardDeviationMs: Double,
    val meanAmplitude: Double,
    val version: Int = 1,
)

enum class BaselineComparison { PERSONAL_BASELINE_NOT_AVAILABLE, STABLE, IMPROVED, DEVIATION_DETECTED, INSUFFICIENT_DATA }

fun compareWithBaseline(
    baseline: PersonalMovementBaseline?,
    exerciseId: String,
    sensorPlacement: String,
    repetitions: List<MovementRepetition>,
): BaselineComparison {
    if (baseline == null) return BaselineComparison.PERSONAL_BASELINE_NOT_AVAILABLE
    if (baseline.exerciseId != exerciseId || baseline.sensorPlacement != sensorPlacement ||
        baseline.sessionCount < 3 || baseline.repetitionCount < 20 || repetitions.isEmpty()
    ) return BaselineComparison.INSUFFICIENT_DATA
    val currentDuration = repetitions.map { it.durationMs.toDouble() }.average()
    val currentAmplitude = repetitions.map { it.amplitude }.average()
    val durationScale = maxOf(baseline.durationStandardDeviationMs, baseline.meanDurationMs * 0.1, 1.0)
    val durationDeviation = abs(currentDuration - baseline.meanDurationMs) / durationScale
    val amplitudeDeviation = abs(currentAmplitude - baseline.meanAmplitude) / maxOf(abs(baseline.meanAmplitude), 0.05)
    return when {
        durationDeviation >= 2.0 || amplitudeDeviation >= 0.5 -> BaselineComparison.DEVIATION_DETECTED
        currentDuration < baseline.meanDurationMs * 0.9 && amplitudeDeviation < 0.2 -> BaselineComparison.IMPROVED
        else -> BaselineComparison.STABLE
    }
}

class RepeatedAnomalyEngine(private val confirmationCount: Int = 3) : MovementRiskSignalProvider {
    private val recent = ArrayDeque<MovementRiskSignal>()

    init {
        require(confirmationCount >= 2)
    }

    fun observe(repetition: MovementRepetition, durationDeviation: Double, amplitudeDeviation: Double): Boolean {
        require(durationDeviation.isFinite() && amplitudeDeviation.isFinite())
        if (durationDeviation < 2.0 && amplitudeDeviation < 0.5) {
            recent.clear()
            return false
        }
        recent.addLast(
            MovementRiskSignal(
                movementRiskSignal = "UNUSUAL_MOVEMENT_PATTERN",
                source = "CALCULATED",
                severity = if (durationDeviation >= 3 || amplitudeDeviation >= 0.8) "MODERATE" else "LOW",
                timestampMs = repetition.endedAtMs,
                evidence = mapOf(
                    "repNumber" to repetition.number.toString(),
                    "durationDeviation" to "elevated",
                    "amplitudeDeviation" to "elevated",
                ),
            ),
        )
        while (recent.size > confirmationCount) recent.removeFirst()
        return recent.size == confirmationCount
    }

    override fun latestSignals(): List<MovementRiskSignal> =
        if (recent.size == confirmationCount) listOf(recent.last()) else emptyList()

    fun reset() = recent.clear()
}

fun movementQuality(
    repetitions: List<MovementRepetition>,
    sensorQuality: SensorQualityMetrics,
): String {
    if (sensorQuality.status == SensorQualityStatus.INSUFFICIENT || repetitions.size < 3) return "INSUFFICIENT_DATA"
    val latest = repetitions.takeLast(5)
    val durations = latest.map { it.durationMs.toDouble() }
    val amplitude = latest.map { it.amplitude }
    val durationCv = coefficientOfVariation(durations)
    val amplitudeCv = coefficientOfVariation(amplitude)
    val smoothness = latest.map { it.smoothness }.average()
    return when {
        durationCv >= 0.35 || amplitudeCv >= 0.5 || smoothness >= 0.22 -> "NEEDS_ATTENTION"
        durationCv >= 0.2 || amplitudeCv >= 0.3 || smoothness >= 0.12 -> "MODERATE"
        else -> "GOOD"
    }
}

fun movementConsistency(repetitions: List<MovementRepetition>): String {
    if (repetitions.size < 3) return "INSUFFICIENT_DATA"
    val variation = coefficientOfVariation(repetitions.takeLast(5).map { it.durationMs.toDouble() })
    return when {
        variation >= 0.35 -> "VARIABLE"
        variation >= 0.2 -> "MODERATE"
        else -> "STABLE"
    }
}

private fun coefficientOfVariation(values: List<Double>): Double {
    if (values.isEmpty()) return Double.POSITIVE_INFINITY
    val mean = values.average()
    if (mean <= 0) return Double.POSITIVE_INFINITY
    return sqrt(values.sumOf { (it - mean) * (it - mean) } / values.size) / mean
}
