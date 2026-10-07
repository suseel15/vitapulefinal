package app.vitapulse.android.core.device

import android.net.Network
import android.os.SystemClock
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flow
import retrofit2.HttpException
import java.io.IOException
import java.util.concurrent.atomic.AtomicBoolean

class HttpPollingMovementDataSource(
    private val repository: Esp32Repository,
    private val pollIntervalMs: Long = 100L,
    private val staleTimeoutMs: Long = 1_500L,
    private val diagnostics: Esp32Diagnostics = Esp32Diagnostics(),
) : MovementDataSource {
    private val _connectionState = MutableStateFlow(MovementConnectionState.DISCONNECTED)
    override val connectionState = _connectionState.asStateFlow()
    private var api: Esp32Api? = null
    private val connected = AtomicBoolean(false)

    init {
        require(pollIntervalMs in 50L..2_000L) { "Polling interval must be 50–2000 ms." }
        require(staleTimeoutMs >= pollIntervalMs * 2) { "Stale timeout must allow at least two polling intervals." }
    }

    suspend override fun connect(network: Network) {
        _connectionState.value = MovementConnectionState.CONNECTING
        val candidate = repository.api(network)
        try {
            val started = SystemClock.elapsedRealtime()
            val firstReading = candidate.getSensorData()
            val sample = validate(firstReading)
            diagnostics.recordSuccess(SystemClock.elapsedRealtime() - started)
            if (sample.source != SensorSource.LIVE_SENSOR) error("Internal source invariant failed.")
            api = candidate
            connected.set(true)
            _connectionState.value = MovementConnectionState.SENSOR_CONNECTED
        } catch (error: SensorStreamException) {
            diagnostics.recordFailure(error)
            _connectionState.value = error.state
            throw error
        } catch (error: CancellationException) {
            _connectionState.value = MovementConnectionState.DISCONNECTED
            throw error
        } catch (error: Exception) {
            diagnostics.recordFailure(error)
            val state = if (error is HttpException || error is IOException) {
                MovementConnectionState.DEVICE_UNREACHABLE
            } else {
                MovementConnectionState.ERROR
            }
            _connectionState.value = state
            throw SensorStreamException(repository.errorType(error), state)
        }
    }

    fun stop() {
        connected.set(false)
        api = null
        _connectionState.value = MovementConnectionState.DISCONNECTED
    }

    override suspend fun disconnect() = stop()

    override suspend fun selectExercise(index: Int) {
        require(index in ESP32_EXERCISES.indices) { "Select one of the supported ESP32 exercises." }
        val activeApi = api ?: throw SensorStreamException(
            "Connect and verify the sensor before selecting an exercise.",
            MovementConnectionState.DISCONNECTED,
        )
        activeApi.selectExercise(index).use { }
    }

    override suspend fun resetExerciseCounter() {
        val activeApi = api ?: throw SensorStreamException(
            "Connect and verify the sensor before resetting repetitions.",
            MovementConnectionState.DISCONNECTED,
        )
        activeApi.resetExerciseCounter().use { }
    }

    override fun readings(): Flow<MovementSample> = flow {
        val activeApi = api ?: throw SensorStreamException("Connect and verify the sensor first.", MovementConnectionState.DISCONNECTED)
        var lastValidAt = SystemClock.elapsedRealtime()
        var consecutiveFailures = 0
        while (connected.get()) {
            currentCoroutineContext().ensureActive()
            val started = SystemClock.elapsedRealtime()
            try {
                val reading = activeApi.getSensorData()
                val receivedAt = SystemClock.elapsedRealtime()
                val sample = validate(reading, receivedAt)
                diagnostics.recordSuccess(receivedAt - started, receivedAt)
                lastValidAt = receivedAt
                consecutiveFailures = 0
                _connectionState.value = MovementConnectionState.SENSOR_CONNECTED
                emit(sample)
                delay(pollIntervalMs)
            } catch (error: SensorStreamException) {
                diagnostics.recordInvalid(error.reason)
                _connectionState.value = error.state
                throw error
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                diagnostics.recordFailure(error)
                consecutiveFailures += 1
                _connectionState.value = MovementConnectionState.RECONNECTING
                if (SystemClock.elapsedRealtime() - lastValidAt >= staleTimeoutMs) {
                    diagnostics.recordStale()
                    throw SensorStreamException("Sensor data is stale. The session has been paused.", MovementConnectionState.DEGRADED)
                }
                if (consecutiveFailures >= MAX_RETRIES) {
                    throw SensorStreamException(repository.errorType(error), MovementConnectionState.DEGRADED)
                }
                delay((pollIntervalMs * (1L shl (consecutiveFailures - 1))).coerceAtMost(MAX_RETRY_DELAY_MS))
            }
        }
    }

    fun diagnostics(internetAvailable: Boolean = false): SensorDiagnostics =
        diagnostics.snapshot(internetAvailable)

    fun resetDiagnostics() = diagnostics.reset()

    private fun validate(
        response: Esp32SensorResponse,
        receivedAtMs: Long = SystemClock.elapsedRealtime(),
    ): MovementSample {
        val axes = listOf(response.ax, response.ay, response.az, response.gx, response.gy, response.gz)
        if (response.mpu != true) {
            throw SensorStreamException("MPU6050 is unavailable.", MovementConnectionState.SENSOR_UNAVAILABLE)
        }
        if (axes.any { it == null || !it.isFinite() }) {
            throw SensorStreamException("Sensor response is missing finite numeric axis values.", MovementConnectionState.DEGRADED)
        }
        val ax = requireNotNull(response.ax)
        val ay = requireNotNull(response.ay)
        val az = requireNotNull(response.az)
        val gx = requireNotNull(response.gx)
        val gy = requireNotNull(response.gy)
        val gz = requireNotNull(response.gz)
        if (listOf(ax, ay, az).any { kotlin.math.abs(it) > 32.0 } ||
            listOf(gx, gy, gz).any { kotlin.math.abs(it) > 4_000.0 }
        ) {
            throw SensorStreamException("Sensor values exceed the supported numeric range.", MovementConnectionState.DEGRADED)
        }
        return MovementSample(
            appTimestamp = System.currentTimeMillis(),
            ax = ax,
            ay = ay,
            az = az,
            gx = gx,
            gy = gy,
            gz = gz,
            source = SensorSource.LIVE_SENSOR,
            deviceId = "ESP32-001",
            sensorType = "MPU6050",
            transport = "HTTP",
            exerciseName = response.exercise?.takeIf { it.isNotBlank() },
            exerciseRepetitions = response.reps?.also {
                if (it < 0) {
                    throw SensorStreamException(
                        "ESP32 exercise repetitions cannot be negative.",
                        MovementConnectionState.DEGRADED,
                    )
                }
            },
            exercisePhase = response.phase?.uppercase()?.also {
                if (it !in SUPPORTED_EXERCISE_PHASES) {
                    throw SensorStreamException(
                        "ESP32 returned an unsupported exercise phase.",
                        MovementConnectionState.DEGRADED,
                    )
                }
            },
            exerciseMotion = response.motion?.uppercase()?.also {
                if (it !in SUPPORTED_EXERCISE_MOTIONS) {
                    throw SensorStreamException(
                        "ESP32 returned an unsupported exercise motion state.",
                        MovementConnectionState.DEGRADED,
                    )
                }
            },
        )
    }

    companion object {
        const val MAX_RETRIES = 8
        const val MAX_RETRY_DELAY_MS = 2_000L
        private val SUPPORTED_EXERCISE_PHASES = setOf("REST", "UP", "DOWN")
        private val SUPPORTED_EXERCISE_MOTIONS = setOf("IDLE", "ACTIVE")
    }
}
