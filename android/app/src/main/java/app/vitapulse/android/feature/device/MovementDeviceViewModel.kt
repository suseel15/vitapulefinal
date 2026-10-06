package app.vitapulse.android.feature.device

import android.app.Application
import android.net.Network
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import app.vitapulse.android.VitaPulseApplication
import app.vitapulse.android.core.device.*
import app.vitapulse.android.movement.data.MovementDatasetExporter
import app.vitapulse.android.movement.features.FEATURE_SCHEMA_VERSION
import app.vitapulse.android.movement.inference.LocalMovementModel
import app.vitapulse.android.movement.session.BaselineComparison
import app.vitapulse.android.movement.session.MovementRepetition
import app.vitapulse.android.movement.session.PersonalMovementBaseline
import app.vitapulse.android.movement.session.compareWithBaseline
import java.util.UUID
import java.time.Instant
import android.net.Uri
import kotlin.math.sqrt
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

data class LiveSessionUi(
    val id: String,
    val backendId: String?,
    val exerciseId: String?,
    val exerciseName: String,
    val placement: String,
    val targetRepetitions: Int,
    val startedAtMs: Long,
    val sampleCount: Int = 0,
    val latestSample: MovementSample? = null,
    val analysis: MovementAnalysis = MovementAnalysis(
        "INSUFFICIENT_DATA", "INSUFFICIENT_DATA", "INSUFFICIENT_DATA", "INSUFFICIENT_DATA", 0,
    ),
    val calibration: SessionCalibration? = null,
    val status: String = "CALIBRATING",
    val syncState: String = "LOCAL_ONLY",
    val error: String? = null,
    val ownerId: String? = null,
    val baseline: PersonalMovementBaseline? = null,
    val baselineComparison: String = "PERSONAL_BASELINE_NOT_AVAILABLE",
    val repetitions: List<MovementRepetition> = emptyList(),
    val anomalies: List<MovementAnomalyRequest> = emptyList(),
    val events: List<MovementEventRequest> = emptyList(),
)

data class MovementDeviceUiState(
    val connectionState: MovementConnectionState = MovementConnectionState.DISCONNECTED,
    val diagnostics: SensorDiagnostics = SensorDiagnostics(),
    val lastSample: MovementSample? = null,
    val graphSamples: List<MovementSample> = emptyList(),
    val registeredDeviceId: String? = null,
    val internetAvailable: Boolean = false,
    val session: LiveSessionUi? = null,
    val localSessions: List<MovementSessionEntity> = emptyList(),
    val busy: Boolean = false,
    val error: String? = null,
    val signedIn: Boolean = false,
    val athleteName: String? = null,
    val exercises: List<ExerciseRecord> = emptyList(),
    val notice: String? = null,
)

class MovementDeviceViewModel(application: Application) : AndroidViewModel(application) {
    private val app = application as VitaPulseApplication
    private val permissionManager = LocalNetworkPermissionManager(application)
    private val calibrationEngine = SessionCalibrationEngine()
    private val _state = MutableStateFlow(MovementDeviceUiState())
    val state = _state.asStateFlow()
    private var sampleBuffer = mutableListOf<MovementSampleEntity>()
    private var pollingJob: kotlinx.coroutines.Job? = null
    private var calibrationJob: kotlinx.coroutines.Job? = null
    private val syncMutex = Mutex()
    private val diagnostics get() = app.movementDataSource.diagnostics(_state.value.internetAvailable)
    private var localModel: LocalMovementModel? = null
    private var lastSavedPredictionTimestamp: Long? = null

    init {
        viewModelScope.launch {
            try {
                val name = app.backendClient.restoreSession()
                if (name != null) {
                    _state.value = _state.value.copy(signedIn = true, athleteName = name)
                    loadExercises()
                    _state.value = _state.value.copy(
                        registeredDeviceId = app.backendClient.registeredDeviceId("ESP32-001"),
                    )
                    syncPendingSessions()
                }
            } catch (error: Exception) {
                setError(error)
            }
        }
        viewModelScope.launch {
            app.networkManager.connectionState.collect {
                _state.value = _state.value.copy(
                    connectionState = it,
                    lastSample = if (it == MovementConnectionState.SENSOR_CONNECTED) _state.value.lastSample else null,
                )
            }
        }
        viewModelScope.launch {
            app.networkManager.internetAvailable.collect {
                _state.value = _state.value.copy(internetAvailable = it)
                if (it && _state.value.signedIn) syncPendingSessions()
            }
        }
        viewModelScope.launch {
            app.movementDatabase.movementDao().sessions().collect {
                _state.value = _state.value.copy(localSessions = it)
            }
        }
    }

    fun permissionToRequest(): String? = permissionManager.permissionToRequest()

    fun signIn(email: String, password: String) {
        viewModelScope.launch {
            updateBusy(true)
            try {
                val name = app.backendClient.signIn(email, password)
                _state.value = _state.value.copy(signedIn = true, athleteName = name, error = null)
                loadExercises()
                _state.value = _state.value.copy(
                    registeredDeviceId = app.backendClient.registeredDeviceId("ESP32-001"),
                )
                syncPendingSessions()
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                setError(error)
            } finally {
                updateBusy(false)
            }
        }
    }

    fun connectDevice(passphrase: String) {
        viewModelScope.launch {
            updateBusy(true)
            try {
                if (permissionManager.permissionToRequest() != null) {
                    app.networkManager.markState(MovementConnectionState.NETWORK_PERMISSION_REQUIRED)
                    error("Grant the requested local Wi-Fi permission before connecting.")
                }
                app.networkManager.requestEsp32Network(passphrase = passphrase)
                val network = withTimeout(NETWORK_TIMEOUT_MS) {
                    app.networkManager.network.first { it != null }
                } ?: error("Android did not provide the ESP32 Wi-Fi network.")
                verifyDevice(network)
                _state.value = _state.value.copy(error = null)
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                val sourceState = app.movementDataSource.connectionState.value
                app.networkManager.markState(
                    when {
                        _state.value.connectionState == MovementConnectionState.NETWORK_PERMISSION_REQUIRED ->
                            MovementConnectionState.NETWORK_PERMISSION_REQUIRED
                        sourceState in setOf(
                            MovementConnectionState.DEVICE_UNREACHABLE,
                            MovementConnectionState.SENSOR_UNAVAILABLE,
                            MovementConnectionState.DEGRADED,
                            MovementConnectionState.ERROR,
                        ) -> sourceState
                        else -> MovementConnectionState.WIFI_CONNECTION_FAILED
                    },
                )
                setError(error)
            } finally {
                updateBusy(false)
            }
        }
    }

    suspend fun verifyDevice(network: Network) {
        app.movementDataSource.connect(network)
        val firstSample = app.movementDataSource.readings().first()
        _state.value = _state.value.copy(
            connectionState = MovementConnectionState.SENSOR_CONNECTED,
            lastSample = firstSample,
            diagnostics = diagnostics,
        )
        app.networkManager.markState(MovementConnectionState.SENSOR_CONNECTED)
    }

    fun testConnection() {
        val network = app.networkManager.network.value
        if (network == null) {
            setError(IllegalStateException("Connect to VitaPulse-ESP32 first."))
            return
        }
        viewModelScope.launch {
            updateBusy(true)
            try {
                verifyDevice(network)
                _state.value = _state.value.copy(error = null, diagnostics = diagnostics)
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                val sourceState = app.movementDataSource.connectionState.value
                app.networkManager.markState(sourceState)
                _state.value = _state.value.copy(
                    connectionState = sourceState,
                    lastSample = null,
                    graphSamples = emptyList(),
                )
                setError(error)
            } finally {
                updateBusy(false)
            }
        }
    }

    fun disconnectDevice() {
        viewModelScope.launch {
            pauseForLifecycle("Sensor disconnected by athlete.")
            app.movementDataSource.disconnect()
            app.networkManager.releaseRequest(manual = true)
            _state.value = _state.value.copy(lastSample = null, error = null)
        }
    }

    fun registerDevice() {
        viewModelScope.launch {
            updateBusy(true)
            try {
                val record = app.backendClient.registerDevice(
                    Esp32Device("ESP32-001", ipAddress = "192.168.4.1"),
                )
                _state.value = _state.value.copy(registeredDeviceId = record.id, error = null)
                syncPendingSessions()
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                setError(error)
            } finally {
                updateBusy(false)
            }
        }
    }

    fun loadExercises() {
        viewModelScope.launch {
            try {
                _state.value = _state.value.copy(exercises = app.backendClient.exercises())
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                _state.value = _state.value.copy(error = error.message ?: "Assigned exercises are unavailable.")
            }
        }
    }

    fun beginLiveSession(exercise: ExerciseRecord, placement: String) {
        calibrationJob = viewModelScope.launch {
            if (_state.value.connectionState != MovementConnectionState.SENSOR_CONNECTED) {
                setError(IllegalStateException("Verify the ESP32 and MPU6050 before starting calibration."))
                return@launch
            }
            updateBusy(true)
            app.movementDataSource.resetDiagnostics()
            _state.value = _state.value.copy(diagnostics = diagnostics, graphSamples = emptyList(), error = null)
            val localId = UUID.randomUUID().toString()
            val startedAt = System.currentTimeMillis()
            var serverSessionId: String? = null
            try {
                var modelWarning: String? = null
                localModel = try {
                    if (_state.value.signedIn) {
                        app.backendClient.syncApprovedMovementModel(app.modelManager)
                    } else {
                        app.modelManager.loadActiveModel()
                    }
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    modelWarning = "Approved exercise recognition is unavailable; deterministic movement analysis will be used. ${error.message}"
                    app.modelManager.loadActiveModel()
                }
                app.movementProcessor.setLocalModel(localModel)
                val ownerId = app.backendClient.currentAthleteId()
                val baselineEntity = if (!ownerId.isNullOrBlank() && exercise.id.isNotBlank()) {
                    withContext(Dispatchers.IO) {
                        app.movementDatabase.movementDao().movementBaseline(ownerId, exercise.id, placement)
                    }
                } else {
                    null
                }
                val baseline = baselineEntity?.let {
                    PersonalMovementBaseline(
                        exerciseId = it.exerciseId,
                        sensorPlacement = it.sensorPlacement,
                        sessionCount = it.sessionCount,
                        repetitionCount = it.repetitionCount,
                        meanDurationMs = it.meanDurationMs,
                        durationStandardDeviationMs = it.durationStandardDeviationMs,
                        meanAmplitude = it.meanAmplitude,
                        version = it.baselineVersion,
                    )
                }
                val deviceId = _state.value.registeredDeviceId
                if (_state.value.signedIn && deviceId != null && exercise.id.isNotBlank()) {
                    try {
                        val backendSession = app.backendClient.createLiveSession(
                            localId,
                            exercise.id,
                            deviceId,
                            placement,
                            exercise.defaultRepetitions ?: 10,
                        )
                        serverSessionId = backendSession.id
                        if (backendSession.status == "PLANNED") {
                            app.backendClient.transitionSession(serverSessionId, "CALIBRATING")
                        }
                    } catch (error: Exception) {
                        _state.value = _state.value.copy(
                            error = "The session will be stored locally and retried when the backend is reachable: ${error.message}",
                        )
                    }
                }
                _state.value = _state.value.copy(
                    session = LiveSessionUi(
                        id = localId,
                        backendId = serverSessionId,
                        exerciseId = exercise.id,
                        exerciseName = exercise.name,
                        placement = placement,
                        targetRepetitions = exercise.defaultRepetitions ?: 10,
                        startedAtMs = startedAt,
                        syncState = if (_state.value.signedIn) "SYNC_PENDING" else "LOCAL_ONLY",
                        ownerId = ownerId,
                        baseline = baseline,
                        baselineComparison = if (baseline == null) {
                            BaselineComparison.PERSONAL_BASELINE_NOT_AVAILABLE.name
                        } else {
                            BaselineComparison.INSUFFICIENT_DATA.name
                        },
                    ),
                    error = modelWarning ?: _state.value.error,
                )
                val calibrationSamples = withTimeout(CALIBRATION_TIMEOUT_MS) {
                    app.movementDataSource.readings().take(CALIBRATION_SAMPLE_COUNT).toList()
                }
                val calibration = calibrationEngine.calibrate(localId, placement, calibrationSamples)
                withContext(Dispatchers.IO) {
                    app.movementDatabase.movementDao().saveCalibration(calibration.asEntity())
                }
                persistSession(
                    _state.value.session?.copy(calibration = calibration),
                    if (serverSessionId == null) "LOCAL_ONLY" else "SYNC_PENDING",
                )
                app.movementProcessor.configureExercise(exercise.name, placement)
                app.movementProcessor.setLocalModel(localModel)
                lastSavedPredictionTimestamp = null
                if (serverSessionId != null) {
                    try {
                        app.backendClient.transitionSession(serverSessionId, "ACTIVE")
                    } catch (error: Exception) {
                        _state.value = _state.value.copy(
                            error = "Calibration completed locally; the backend session state will retry: ${error.message}",
                        )
                    }
                }
                val active = requireNotNull(_state.value.session).copy(
                    calibration = calibration,
                    status = "ACTIVE",
                    startedAtMs = System.currentTimeMillis(),
                    syncState = if (serverSessionId == null && !_state.value.signedIn) "LOCAL_ONLY" else "SYNC_PENDING",
                )
                _state.value = _state.value.copy(
                    session = active,
                    error = if (serverSessionId == null && _state.value.signedIn) {
                        _state.value.error ?: "Session is local until it can be synchronized."
                    } else if (serverSessionId != null) {
                        _state.value.error
                    } else {
                        null
                    },
                )
                persistSession(active, active.syncState)
                startPolling(active)
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                val backendError = if (serverSessionId != null) {
                    try {
                        app.backendClient.transitionSession(serverSessionId, "ERROR")
                        null
                    } catch (transitionError: Exception) {
                        transitionError.message ?: "The backend could not mark calibration as failed."
                    }
                } else {
                    null
                }
                val message = error.message ?: "Calibration failed. Keep the sensor still and try again."
                _state.value = _state.value.copy(
                    session = _state.value.session?.copy(status = "CALIBRATION_FAILED", error = backendError ?: message),
                    error = backendError ?: message,
                )
                persistSession(_state.value.session, "SYNC_FAILED")
            } finally {
                updateBusy(false)
            }
        }
    }

    private fun startPolling(session: LiveSessionUi) {
        val dao = app.movementDatabase.movementDao()
        pollingJob = viewModelScope.launch {
            try {
                app.movementDataSource.readings().collect { sample ->
                    val analysis = app.movementProcessor.add(sample, session.calibration)
                    val current = _state.value.session ?: return@collect
                    val completedRepetitions = app.movementProcessor.completedRepetitions
                    val newRepetition = completedRepetitions.lastOrNull()
                        ?.takeIf { it.number > current.analysis.repetitionCount }
                    val baselineStatus = if (current.baseline != null && current.exerciseId != null) {
                        compareWithBaseline(
                            current.baseline,
                            current.exerciseId,
                            current.placement,
                            completedRepetitions,
                        ).name
                    } else {
                        BaselineComparison.PERSONAL_BASELINE_NOT_AVAILABLE.name
                    }
                    val updatedAnomalies = current.anomalies.toMutableList()
                    val updatedEvents = current.events.toMutableList()
                    newRepetition?.let { repetition ->
                        updatedEvents += MovementEventRequest(
                            timestamp = repetition.endedAtMs,
                            eventType = "REP_COMPLETED",
                            severity = when (repetition.quality.name) {
                                "NEEDS_ATTENTION" -> "MODERATE"
                                else -> "LOW"
                            },
                            description = "Repetition ${repetition.number} completed with ${repetition.quality.name.lowercase().replace('_', ' ')} movement consistency.",
                            source = "CALCULATED",
                        )
                        withContext(Dispatchers.IO) {
                            dao.saveRepetitions(
                                listOf(
                                    MovementRepetitionEntity(
                                        sessionId = session.id,
                                        repNumber = repetition.number,
                                        startedAtMs = repetition.startedAtMs,
                                        endedAtMs = repetition.endedAtMs,
                                        durationMs = repetition.durationMs,
                                        quality = repetition.quality.name,
                                        amplitude = repetition.amplitude,
                                        smoothness = repetition.smoothness,
                                        source = repetition.source,
                                    ),
                                ),
                            )
                            dao.saveEvent(
                                MovementEventEntity(
                                    id = "${session.id}:rep:${repetition.number}",
                                    sessionId = session.id,
                                    timestampMs = repetition.endedAtMs,
                                    eventType = "REP_COMPLETED",
                                    severity = if (repetition.quality.name == "NEEDS_ATTENTION") "MODERATE" else "LOW",
                                    description = "Repetition ${repetition.number} completed; quality ${repetition.quality.name}.",
                                    source = "CALCULATED",
                                ),
                            )
                        }
                        if (app.movementProcessor.latestAnomalyDetected) {
                            val risk = app.movementProcessor.latestSignals().lastOrNull()
                            if (risk != null && updatedAnomalies.none { it.eventTimestamp == risk.timestampMs }) {
                                updatedAnomalies += MovementAnomalyRequest(
                                    eventTimestamp = risk.timestampMs,
                                    severity = risk.severity,
                                    baselineDeviation = null,
                                    modelName = null,
                                    modelVersion = null,
                                    requiresReview = true,
                                )
                                updatedEvents += MovementEventRequest(
                                    timestamp = risk.timestampMs,
                                    eventType = "ANOMALY_DETECTED",
                                    severity = risk.severity,
                                    description = "A repeated unusual movement pattern was observed. This is not a diagnosis.",
                                    source = "CALCULATED",
                                )
                                withContext(Dispatchers.IO) {
                                    dao.saveEvent(
                                        MovementEventEntity(
                                            id = "${session.id}:anomaly:${risk.timestampMs}",
                                            sessionId = session.id,
                                            timestampMs = risk.timestampMs,
                                            eventType = "ANOMALY_DETECTED",
                                            severity = risk.severity,
                                            description = "A repeated unusual movement pattern was observed.",
                                            source = "CALCULATED",
                                        ),
                                    )
                                }
                            }
                        }
                    }
                    val updated = current.copy(
                        sampleCount = current.sampleCount + 1,
                        latestSample = sample,
                        analysis = analysis,
                        repetitions = completedRepetitions,
                        baselineComparison = baselineStatus,
                        anomalies = updatedAnomalies.takeLast(50),
                        events = updatedEvents.takeLast(200),
                        error = null,
                    )
                    _state.value = _state.value.copy(
                        connectionState = app.movementDataSource.connectionState.value,
                        session = updated,
                        lastSample = sample,
                        graphSamples = (_state.value.graphSamples + sample).takeLast(GRAPH_SAMPLE_LIMIT),
                        diagnostics = diagnostics,
                    )
                    app.movementProcessor.latestPrediction?.let { prediction ->
                        if (prediction.timestampMs != lastSavedPredictionTimestamp) {
                            lastSavedPredictionTimestamp = prediction.timestampMs
                            withContext(Dispatchers.IO) {
                                dao.savePrediction(
                                    MovementPredictionEntity(
                                        id = "${session.id}:${prediction.timestampMs}",
                                        sessionId = session.id,
                                        exercise = prediction.exercise.name,
                                        modelName = prediction.modelName,
                                        modelVersion = prediction.modelVersion,
                                        featureSchemaVersion = FEATURE_SCHEMA_VERSION,
                                        timestampMs = prediction.timestampMs,
                                        source = prediction.source.name,
                                    ),
                                )
                            }
                        }
                    }
                    sampleBuffer += MovementSampleEntity(
                        sessionId = session.id,
                        appTimestamp = sample.appTimestamp,
                        ax = sample.ax,
                        ay = sample.ay,
                        az = sample.az,
                        gx = sample.gx,
                        gy = sample.gy,
                        gz = sample.gz,
                    )
                    if (sampleBuffer.size >= SAMPLE_BATCH_SIZE) {
                        val batch = sampleBuffer.toList()
                        sampleBuffer.clear()
                        withContext(Dispatchers.IO) { dao.saveBoundedSamples(session.id, batch) }
                    }
                }
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                app.networkManager.markState(app.movementDataSource.connectionState.value)
                sampleBuffer.takeIf { it.isNotEmpty() }?.toList()?.let {
                    withContext(Dispatchers.IO) { dao.saveBoundedSamples(session.id, it) }
                    sampleBuffer.clear()
                }
                _state.value = _state.value.copy(
                    connectionState = app.movementDataSource.connectionState.value,
                    lastSample = null,
                    graphSamples = emptyList(),
                    session = _state.value.session?.copy(
                        status = "PAUSED",
                        error = error.message ?: "Sensor connection was interrupted. Session paused.",
                    ),
                    error = error.message ?: "Sensor connection was interrupted. Session paused.",
                    diagnostics = diagnostics,
                )
                persistSession(_state.value.session, "SYNC_PENDING")
            }
        }
    }

    fun pauseSession() {
        viewModelScope.launch { pauseSession("Session paused by athlete.") }
    }

    fun pauseForBackground() {
        viewModelScope.launch { pauseForLifecycle("App moved to background; live sensor polling paused.") }
    }

    private suspend fun pauseForLifecycle(reason: String) {
        val session = _state.value.session
        if (session?.status != "CALIBRATING") {
            pauseSession(reason)
            return
        }
        calibrationJob?.cancel()
        val failed = session.copy(status = "CALIBRATION_FAILED", error = reason)
        _state.value = _state.value.copy(session = failed, error = reason)
        if (session.backendId != null) {
            try {
                app.backendClient.transitionSession(session.backendId, "ERROR")
            } catch (error: Exception) {
                _state.value = _state.value.copy(
                    error = error.message ?: "Calibration stopped locally; backend status could not be synchronized.",
                )
            }
        }
        persistSession(failed, "SYNC_FAILED")
    }

    private suspend fun pauseSession(reason: String) {
        val current = _state.value.session ?: return
        if (current.status !in setOf("ACTIVE", "PAUSED")) return
        pollingJob?.cancel()
        pollingJob?.join()
        pollingJob = null
        sampleBuffer.takeIf { it.isNotEmpty() }?.toList()?.let {
            withContext(Dispatchers.IO) {
                app.movementDatabase.movementDao().saveBoundedSamples(current.id, it)
            }
            sampleBuffer.clear()
        }
        val backendError = if (current.status == "ACTIVE" && current.backendId != null) {
            try {
                app.backendClient.transitionSession(current.backendId, "PAUSED")
                null
            } catch (error: Exception) {
                error.message ?: "Could not sync the paused state to the backend."
            }
        } else {
            null
        }
        _state.value = _state.value.copy(
            session = current.copy(
                status = "PAUSED",
                syncState = if (backendError == null) current.syncState else "SYNC_PENDING",
                error = backendError ?: reason,
            ),
            error = backendError ?: reason,
        )
        persistSession(
            _state.value.session,
            if (backendError == null) current.syncState else "SYNC_PENDING",
        )
    }

    fun resumeSession() {
        val session = _state.value.session ?: return
        if (session.status != "PAUSED") return
        viewModelScope.launch {
            try {
                val network = app.networkManager.network.value ?: error("Reconnect to the ESP32 before resuming.")
                verifyDevice(network)
                session.backendId?.let { app.backendClient.transitionSession(it, "ACTIVE") }
                val resumed = session.copy(status = "ACTIVE", error = null)
                _state.value = _state.value.copy(session = resumed, error = null)
                startPolling(resumed)
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                setError(error)
            }
        }
    }

    fun endSession() {
        viewModelScope.launch {
            val current = _state.value.session ?: return@launch
            pauseSession("Session ended.")
            val stopped = _state.value.session ?: current
            val diagnostics = diagnostics
            val summary = app.movementProcessor.summarize()
            val canSync = !current.exerciseId.isNullOrBlank() &&
                (current.backendId != null || _state.value.signedIn)
            val syncState = if (canSync) "SYNC_PENDING" else "LOCAL_ONLY"
            val completed = stopped.copy(
                status = "COMPLETED",
                analysis = summary,
                repetitions = app.movementProcessor.completedRepetitions,
                syncState = syncState,
                error = null,
            )
            persistSession(completed, syncState, diagnostics)
            val updatedBaseline = updatePersonalBaseline(completed)
            val completedForUi = completed.copy(
                baseline = updatedBaseline?.toPersonalBaseline() ?: completed.baseline,
            )
            if (completedForUi != completed) persistSession(completedForUi, syncState, diagnostics)
            _state.value = _state.value.copy(session = completedForUi)
            if (canSync) {
                syncCompletedRecord(toEntity(completedForUi, syncState, diagnostics))
            }
        }
    }

    fun exportCurrentSessionDataset(destination: Uri) {
        val sessionId = _state.value.session
            ?.takeIf { it.status == "COMPLETED" }
            ?.id
            ?: return setError(IllegalStateException("Complete a live sensor session before exporting its training sample."))
        viewModelScope.launch {
            try {
                val pseudonymousAthleteId = app.backendClient.datasetPseudonymousAthleteId()
                val session = requireNotNull(app.movementDatabase.movementDao().session(sessionId)) {
                    "The completed movement session could not be found on this device."
                }
                val samples = app.movementDatabase.movementDao().recentSamples(sessionId)
                val exported = withContext(Dispatchers.IO) {
                    val stream = requireNotNull(app.contentResolver.openOutputStream(destination)) {
                        "The selected dataset file could not be opened."
                    }
                    stream.use {
                        MovementDatasetExporter.writeArchive(
                            it,
                            session,
                            samples,
                            pseudonymousAthleteId,
                        )
                    }
                }
                _state.value = _state.value.copy(
                    error = null,
                    notice = "Exported $exported live sensor samples. Keep the ZIP private; it contains raw movement data.",
                )
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                setError(error)
            }
        }
    }

    private suspend fun persistSession(
        session: LiveSessionUi?,
        syncState: String,
        diagnostics: SensorDiagnostics = this.diagnostics,
    ) {
        if (session == null) return
        withContext(Dispatchers.IO) {
            app.movementDatabase.movementDao().saveSession(toEntity(session, syncState, diagnostics))
        }
    }

    private fun toEntity(
        session: LiveSessionUi,
        syncState: String,
        diagnostics: SensorDiagnostics,
    ): MovementSessionEntity = MovementSessionEntity(
        id = session.id,
        exerciseName = session.exerciseName,
        exerciseId = session.exerciseId,
        deviceIdentifier = "ESP32-001",
        registeredDeviceId = _state.value.registeredDeviceId,
        sensorType = "MPU6050",
        transport = "HTTP",
        source = "LIVE_SENSOR",
        sensorPlacement = session.placement,
        targetRepetitions = session.targetRepetitions,
        backendSessionId = session.backendId,
        status = session.status,
        startedAtMs = session.startedAtMs,
        endedAtMs = if (session.status == "COMPLETED") System.currentTimeMillis() else null,
        sampleCount = session.sampleCount,
        successfulRequests = diagnostics.successfulRequests.toInt(),
        failedRequests = diagnostics.failedRequests.toInt(),
        invalidSamples = diagnostics.invalidSamples.toInt(),
        averageLatencyMs = diagnostics.averageLatencyMs,
        measuredRateHz = diagnostics.measuredRateHz,
        movementQuality = session.analysis.movementQuality,
        stability = session.analysis.stability,
        smoothness = session.analysis.smoothness,
        fatigueSignal = session.analysis.fatigueSignal,
        repetitions = session.analysis.repetitionCount,
        syncState = syncState,
        ownerId = session.ownerId,
        consistency = session.analysis.consistency,
        sensorQuality = session.analysis.sensorQuality,
        recognition = session.analysis.recognition,
        recognizedExercise = session.analysis.recognizedExercise,
        modelName = app.movementProcessor.latestPrediction?.modelName,
        modelVersion = session.analysis.modelVersion,
        baselineStatus = session.baselineComparison,
        anomalyCount = session.anomalies.size,
    )

    private suspend fun updatePersonalBaseline(session: LiveSessionUi): MovementBaselineEntity? {
        val ownerId = session.ownerId ?: return null
        val exerciseId = session.exerciseId?.takeIf { it.isNotBlank() } ?: return null
        if (session.sampleCount < MINIMUM_BASELINE_SAMPLES ||
            session.analysis.sensorQuality !in setOf("EXCELLENT", "GOOD") ||
            session.analysis.movementQuality == "INSUFFICIENT_DATA"
        ) return null
        val dao = app.movementDatabase.movementDao()
        val validSessions = withContext(Dispatchers.IO) {
            dao.eligibleBaselineSessions(ownerId, exerciseId, session.placement)
        }
        val validRepetitions = withContext(Dispatchers.IO) {
            dao.eligibleBaselineRepetitions(ownerId, exerciseId, session.placement)
        }
        if (validSessions.size < MINIMUM_BASELINE_SESSIONS ||
            validRepetitions.size < MINIMUM_BASELINE_REPETITIONS
        ) return null
        val durations = validRepetitions.map { it.durationMs.toDouble() }
        val meanDuration = durations.average()
        val durationDeviation = sqrt(
            durations.sumOf { (it - meanDuration) * (it - meanDuration) } / durations.size,
        )
        val existing = withContext(Dispatchers.IO) {
            dao.movementBaseline(ownerId, exerciseId, session.placement)
        }
        val baseline = MovementBaselineEntity(
            ownerId = ownerId,
            exerciseId = exerciseId,
            sensorPlacement = session.placement,
            baselineVersion = (existing?.baselineVersion ?: 0) + 1,
            sessionCount = validSessions.map { it.id }.distinct().size,
            repetitionCount = durations.size,
            meanDurationMs = meanDuration,
            durationStandardDeviationMs = durationDeviation,
            meanAmplitude = validRepetitions.map { it.amplitude }.average(),
            updatedAtMs = System.currentTimeMillis(),
            status = "AVAILABLE",
        )
        withContext(Dispatchers.IO) { dao.saveBaseline(baseline) }
        return baseline
    }

    private fun MovementBaselineEntity.toPersonalBaseline() = PersonalMovementBaseline(
        exerciseId = exerciseId,
        sensorPlacement = sensorPlacement,
        sessionCount = sessionCount,
        repetitionCount = repetitionCount,
        meanDurationMs = meanDurationMs,
        durationStandardDeviationMs = durationStandardDeviationMs,
        meanAmplitude = meanAmplitude,
        version = baselineVersion,
    )

    fun syncPendingSessions() {
        viewModelScope.launch {
            if (_state.value.registeredDeviceId == null && _state.value.signedIn) {
                try {
                    _state.value = _state.value.copy(
                        registeredDeviceId = app.backendClient.registeredDeviceId("ESP32-001"),
                    )
                } catch (error: Exception) {
                    setError(error)
                }
            }
            val pending = withContext(Dispatchers.IO) {
                app.movementDatabase.movementDao().pendingSessions()
            }
            pending.forEach { syncCompletedRecord(it) }
        }
    }

    private suspend fun syncCompletedRecord(record: MovementSessionEntity) {
        var recordToSave = record
        syncMutex.withLock {
            try {
                val exerciseId = requireNotNull(record.exerciseId) { "The exercise is missing; this session cannot be synchronized." }
                val deviceId = record.registeredDeviceId
                    ?: _state.value.registeredDeviceId
                    ?: error("Register ESP32-001 to this account before syncing.")
                var backendId = record.backendSessionId
                var backendStatus: String
                if (backendId == null) {
                    val created = app.backendClient.createLiveSession(
                        record.id,
                        exerciseId,
                        deviceId,
                        record.sensorPlacement,
                        record.targetRepetitions,
                    )
                    backendId = created.id
                    backendStatus = created.status
                    recordToSave = record.copy(backendSessionId = backendId, registeredDeviceId = deviceId)
                    withContext(Dispatchers.IO) {
                        app.movementDatabase.movementDao().saveSession(recordToSave)
                    }
                } else {
                    backendStatus = app.backendClient.sessionStatus(backendId)
                }
                if (backendStatus == "PLANNED") {
                    app.backendClient.transitionSession(backendId, "CALIBRATING")
                    backendStatus = "CALIBRATING"
                }
                if (backendStatus in setOf("CALIBRATING", "PAUSED")) {
                    app.backendClient.transitionSession(backendId, "ACTIVE")
                    backendStatus = "ACTIVE"
                }
                check(backendStatus in setOf("ACTIVE", "COMPLETED")) {
                    "The backend session is $backendStatus and cannot accept this summary."
                }
                val dao = app.movementDatabase.movementDao()
                val storedRepetitions = withContext(Dispatchers.IO) { dao.repetitions(record.id) }
                val storedEvents = withContext(Dispatchers.IO) { dao.events(record.id) }
                val latestPrediction = withContext(Dispatchers.IO) { dao.latestPrediction(record.id) }
                app.backendClient.uploadMovementSummary(
                    backendId,
                    MovementSummaryRequest(
                        sensorPlacement = record.sensorPlacement,
                        sampleCount = record.sampleCount,
                        targetRepetitions = record.targetRepetitions,
                        completedRepetitions = record.repetitions,
                        movementQuality = record.movementQuality,
                        stability = record.stability,
                        smoothness = record.smoothness,
                        fatigueSignal = record.fatigueSignal,
                        sessionDurationSeconds = ((record.endedAtMs ?: System.currentTimeMillis()) - record.startedAtMs)
                            .div(1_000).toInt().coerceIn(0, 86_400),
                        deviceId = deviceId,
                        successfulRequests = record.successfulRequests,
                        failedRequests = record.failedRequests,
                        invalidSamples = record.invalidSamples,
                        measuredRateHz = record.measuredRateHz,
                        averageLatencyMs = record.averageLatencyMs,
                        repetitions = storedRepetitions.take(200).map { repetition ->
                            MovementRepetitionRequest(
                                repNumber = repetition.repNumber,
                                startedAt = Instant.ofEpochMilli(repetition.startedAtMs).toString(),
                                endedAt = Instant.ofEpochMilli(repetition.endedAtMs).toString(),
                                durationMs = repetition.durationMs,
                                movementPhase = null,
                                quality = repetition.quality,
                                stability = repetition.quality,
                                smoothness = if (repetition.smoothness < 0.12) "GOOD" else "MODERATE",
                                rangeOfMotionSignal = null,
                                abnormality = null,
                                source = repetition.source,
                            )
                        },
                        movementIntelligence = MovementIntelligenceRequest(
                            exerciseRecognitionStatus = record.recognition ?: "MODEL_UNAVAILABLE",
                            recognizedExercise = record.recognizedExercise,
                            predictionSource = if (record.recognition == "RECOGNIZED") "MODEL_INFERRED" else null,
                            modelName = latestPrediction?.modelName ?: record.modelName,
                            modelVersion = latestPrediction?.modelVersion ?: record.modelVersion,
                            featureSchemaVersion = latestPrediction?.featureSchemaVersion,
                            predictionTimestamp = latestPrediction?.timestampMs,
                            consistency = record.consistency ?: "INSUFFICIENT_DATA",
                            sensorQualityStatus = record.sensorQuality ?: "INSUFFICIENT",
                            baselineStatus = record.baselineStatus ?: "PERSONAL_BASELINE_NOT_AVAILABLE",
                            calculationVersion = "movement-analysis-v1",
                            anomalies = storedEvents.filter { it.eventType == "ANOMALY_DETECTED" }.takeLast(50).map { event ->
                                MovementAnomalyRequest(
                                    eventTimestamp = event.timestampMs,
                                    severity = event.severity,
                                    baselineDeviation = null,
                                    modelName = null,
                                    modelVersion = null,
                                    requiresReview = true,
                                )
                            },
                            events = storedEvents.takeLast(200).map { event ->
                                MovementEventRequest(
                                    timestamp = event.timestampMs,
                                    eventType = event.eventType,
                                    severity = event.severity,
                                    description = event.description,
                                    source = event.source,
                                )
                            },
                        ),
                    ),
                )
                if (backendStatus != "COMPLETED") app.backendClient.transitionSession(backendId, "COMPLETED")
                val synced = recordToSave.copy(
                    backendSessionId = backendId,
                    registeredDeviceId = deviceId,
                    syncState = "SYNCED",
                )
                withContext(Dispatchers.IO) { app.movementDatabase.movementDao().saveSession(synced) }
                if (_state.value.session?.id == record.id) {
                    _state.value = _state.value.copy(session = _state.value.session?.copy(
                        backendId = backendId,
                        syncState = "SYNCED",
                    ))
                }
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                val failed = recordToSave.copy(syncState = "SYNC_FAILED")
                withContext(Dispatchers.IO) { app.movementDatabase.movementDao().saveSession(failed) }
                if (_state.value.session?.id == record.id) {
                    _state.value = _state.value.copy(
                        session = _state.value.session?.copy(syncState = "SYNC_FAILED"),
                        error = error.message ?: "Session summary sync failed.",
                    )
                }
            }
        }
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }

    fun permissionDenied() {
        _state.value = _state.value.copy(
            connectionState = MovementConnectionState.NETWORK_PERMISSION_REQUIRED,
            error = "Local Wi-Fi permission was denied. Allow it to connect to VitaPulse-ESP32.",
        )
    }

    private fun setError(error: Throwable) {
        _state.value = _state.value.copy(
            error = error.message ?: error.javaClass.simpleName,
            notice = null,
        )
    }

    private fun updateBusy(busy: Boolean) {
        _state.value = _state.value.copy(busy = busy)
    }

    override fun onCleared() {
        calibrationJob?.cancel()
        pollingJob?.cancel()
        app.movementDataSource.stop()
        app.networkManager.releaseRequest(manual = true)
        super.onCleared()
    }

    companion object {
        private const val NETWORK_TIMEOUT_MS = 30_000L
        private const val CALIBRATION_TIMEOUT_MS = 30_000L
        private const val CALIBRATION_SAMPLE_COUNT = 30
        private const val SAMPLE_BATCH_SIZE = 10
        private const val GRAPH_SAMPLE_LIMIT = 100
        private const val MINIMUM_BASELINE_SESSIONS = 3
        private const val MINIMUM_BASELINE_REPETITIONS = 20
        private const val MINIMUM_BASELINE_SAMPLES = 20
    }
}
