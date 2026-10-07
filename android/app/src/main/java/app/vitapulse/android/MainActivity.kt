package app.vitapulse.android

import android.Manifest
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.HealthAndSafety
import androidx.compose.material.icons.filled.Assessment
import androidx.compose.material.icons.filled.Sensors
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.viewmodel.compose.viewModel
import app.vitapulse.android.core.device.ExerciseRecord
import app.vitapulse.android.core.device.MovementConnectionState
import app.vitapulse.android.core.device.MovementSample
import app.vitapulse.android.feature.device.MovementDeviceViewModel
import app.vitapulse.android.feature.connect.ConnectFeatureScreen
import app.vitapulse.android.feature.connect.ConnectedHealthContextCard
import app.vitapulse.android.feature.reports.ReportsFeatureScreen
import java.util.Locale

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(Modifier.fillMaxSize(), color = Color(0xFFF6F8F7)) {
                    VitaPulseRoot()
                }
            }
        }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun VitaPulseRoot(deviceViewModel: MovementDeviceViewModel = viewModel()) {
    val state by deviceViewModel.state.collectAsStateWithLifecycle()
    val lifecycleOwner = LocalLifecycleOwner.current
    var tab by remember { mutableStateOf("web") }
    var webView by remember { mutableStateOf<android.webkit.WebView?>(null) }
    var webCanGoBack by remember { mutableStateOf(false) }
    var showConnectDialog by remember { mutableStateOf(false) }
    var showDiagnostics by remember { mutableStateOf(false) }
    var showSignIn by remember { mutableStateOf(false) }
    var password by remember { mutableStateOf("") }
    var showDatasetLabelConfirmation by remember { mutableStateOf(false) }

    val datasetExportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/zip"),
    ) { uri ->
        if (uri != null) deviceViewModel.exportCurrentSessionDataset(uri)
    }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) deviceViewModel.pauseForBackground()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            deviceViewModel.connectDevice(password)
            password = ""
            showConnectDialog = false
        } else {
            deviceViewModel.permissionDenied()
        }
    }

    BackHandler(enabled = tab == "web" && webCanGoBack) {
        webView?.goBack()
    }
    BackHandler(enabled = tab == "device") {
        tab = "connect"
    }

    Scaffold(
        topBar = {
            if (tab != "web") {
                TopAppBar(
                    title = {
                        Column {
                            Text("vitapulse", style = MaterialTheme.typography.titleLarge)
                            Text("ATHLETE WELLBEING · PHASE 9", style = MaterialTheme.typography.labelSmall)
                        }
                    },
                )
            }
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    selected = tab == "web",
                    onClick = { tab = "web" },
                    icon = { Icon(Icons.Default.Home, contentDescription = null) },
                    label = { Text("Home") },
                )
                NavigationBarItem(
                    selected = tab == "health",
                    onClick = { tab = "health" },
                    icon = { Icon(Icons.Default.HealthAndSafety, contentDescription = null) },
                    label = { Text("Health") },
                )
                NavigationBarItem(
                    selected = tab == "reports",
                    onClick = { tab = "reports" },
                    icon = { Icon(Icons.Default.Assessment, contentDescription = null) },
                    label = { Text("Reports") },
                )
                NavigationBarItem(
                    selected = tab == "rehab",
                    onClick = { tab = "rehab" },
                    icon = { Icon(Icons.Default.FitnessCenter, contentDescription = null) },
                    label = { Text("Rehab") },
                )
                NavigationBarItem(
                    selected = tab == "wellbeing",
                    onClick = { tab = "wellbeing" },
                    icon = { Icon(Icons.Default.Favorite, contentDescription = null) },
                    label = { Text("Wellbeing") },
                )
                NavigationBarItem(
                    selected = tab == "connect" || tab == "device",
                    onClick = { tab = "connect" },
                    icon = { Icon(Icons.Default.Sensors, contentDescription = null) },
                    label = { Text("Connect") },
                )
            }
        },
    ) { insets ->
        Box(Modifier.fillMaxSize().padding(insets)) {
            VitaPulseWebApp(
                url = BuildConfig.WEB_APP_URL,
                visible = tab == "web",
                modifier = Modifier.fillMaxSize(),
                onWebViewCreated = { webView = it },
                onCanGoBackChange = { webCanGoBack = it },
            )
            if (tab == "wellbeing") {
                app.vitapulse.android.feature.wellbeing.WellbeingFeatureScreen(
                    modifier = Modifier.fillMaxSize(),
                    onOpenConnect = { tab = "connect" },
                )
            } else if (tab == "reports") {
                ReportsFeatureScreen(
                    signedIn = state.signedIn,
                    onSignIn = { showSignIn = true },
                    modifier = Modifier.fillMaxSize(),
                )
            } else if (tab == "health") {
                ConnectFeatureScreen(
                    movementState = state.connectionState,
                    onOpenMovementDevice = { tab = "device" },
                    onTestMovementDevice = deviceViewModel::testConnection,
                    initialRoute = "health-data",
                    modifier = Modifier.fillMaxSize(),
                )
            } else if (tab == "connect") {
                ConnectFeatureScreen(
                    movementState = state.connectionState,
                    onOpenMovementDevice = { tab = "device" },
                    onTestMovementDevice = deviceViewModel::testConnection,
                    modifier = Modifier.fillMaxSize(),
                )
            } else if (tab == "device") {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(horizontal = 18.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item {
                        TextButton(onClick = { tab = "connect" }) {
                            Icon(Icons.Default.Home, contentDescription = "Back")
                            Text("Back to Connect")
                        }
                    }
                    item {
                        if (state.error != null) NoticeCard(state.error!!, isError = true)
                        state.notice?.let { NoticeCard(it, isError = false) }
                        DeviceScreen(
                            state = state,
                            showDiagnostics = showDiagnostics,
                            onConnect = { showConnectDialog = true },
                            onDisconnect = deviceViewModel::disconnectDevice,
                            onTest = deviceViewModel::testConnection,
                            onRegister = deviceViewModel::registerDevice,
                            onDiagnostics = { showDiagnostics = !showDiagnostics },
                            onSignIn = { showSignIn = true },
                        )
                    }
                }
            } else if (tab != "web") {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(horizontal = 18.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item {
                        ConnectedHealthContextCard(
                            title = "Recovery context",
                            onOpenConnect = { tab = "connect" },
                        )
                    }
                    item {
                        if (state.error != null) {
                            NoticeCard(state.error!!, isError = true)
                        }
                        state.notice?.let { NoticeCard(it, isError = false) }
                    }
                    if (state.session?.status == "COMPLETED") {
                        val completedSession = checkNotNull(state.session)
                        item {
                            Card(colors = CardDefaults.cardColors(containerColor = Color.White)) {
                                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                    Text("Movement insights", style = MaterialTheme.typography.titleLarge)
                                    Text(completedSession.exerciseName, style = MaterialTheme.typography.titleMedium)
                                    Text("${completedSession.analysis.repetitionCount} repetitions completed")
                                    Text("Movement quality  ${completedSession.analysis.movementQuality}")
                                    Text("Stability  ${completedSession.analysis.stability} · smoothness  ${completedSession.analysis.smoothness}")
                                    Text("Consistency  ${completedSession.analysis.consistency}")
                                    Text("Movement-based fatigue signal  ${completedSession.analysis.fatigueSignal}")
                                    Text("Sensor quality  ${completedSession.analysis.sensorQuality}")
                                    MovementBaselineSummary(completedSession)
                                    if (completedSession.anomalies.isNotEmpty()) {
                                        Text("A repeated unusual movement pattern was observed. Consider reviewing your form.")
                                        Text("This is a movement signal, not a diagnosis.")
                                    } else {
                                        Text("No repeated unusual movement pattern was confirmed in this session.")
                                    }
                                    RepByRepSummary(completedSession.repetitions.map { it.number to it.quality.name })
                                    if (BuildConfig.DEBUG && state.signedIn && completedSession.sampleCount >= 30) {
                                        Text(
                                            "Developer data collection: export this live session as a manually labeled sample. " +
                                                "The ZIP contains raw sensor data and is not uploaded.",
                                            style = MaterialTheme.typography.bodySmall,
                                        )
                                        OutlinedButton(onClick = { showDatasetLabelConfirmation = true }) {
                                            Text("Export training sample")
                                        }
                                    }
                                    Text(
                                        "Movement intelligence is based on sensor-derived signals and is not a medical diagnosis.",
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                }
                            }
                        }
                    } else {
                        item {
                            RehabScreen(
                                state = state,
                                onLoadExercises = deviceViewModel::loadExercises,
                                onStart = deviceViewModel::beginLiveSession,
                                onPause = deviceViewModel::pauseSession,
                                onResume = deviceViewModel::resumeSession,
                                onEnd = deviceViewModel::endSession,
                            )
                        }
                    }
                }
            }
        }
    }

    if (showConnectDialog) {
        AlertDialog(
            onDismissRequest = { showConnectDialog = false },
            title = { Text("Connect to VitaPulse-ESP32") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Android will ask to join the sensor's local Wi-Fi. Internet is not needed for sensor use.")
                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = { Text("Wi-Fi password") },
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                        singleLine = true,
                    )
                    Text("The Wi-Fi password is used only for this Android network request and is not saved.")
                }
            },
            confirmButton = {
                Button(enabled = password.isNotBlank(), onClick = {
                    val required = deviceViewModel.permissionToRequest()
                    if (required != null) permissionLauncher.launch(required)
                    else {
                        deviceViewModel.connectDevice(password)
                        password = ""
                        showConnectDialog = false
                    }
                }) { Text("Continue") }
            },
            dismissButton = { TextButton(onClick = { showConnectDialog = false }) { Text("Cancel") } },
        )
    }
    if (showSignIn) {
        SignInDialog(
            onDismiss = { showSignIn = false },
            onSignIn = { email, password ->
                deviceViewModel.signIn(email, password)
                showSignIn = false
            },
        )
    }
    if (showDatasetLabelConfirmation) {
        val session = state.session
        AlertDialog(
            onDismissRequest = { showDatasetLabelConfirmation = false },
            title = { Text("Confirm the manual exercise label") },
            text = {
                Text(
                    "The entire recording will be labeled ${session?.exerciseName ?: "with this exercise"}. " +
                        "Confirm that the completed live session contains only that exercise before exporting it.",
                )
            },
            confirmButton = {
                Button(enabled = session?.status == "COMPLETED", onClick = {
                    if (session != null) {
                        val name = session.exerciseName.lowercase(Locale.US)
                            .replace(Regex("[^a-z0-9]+"), "_")
                            .trim('_')
                        datasetExportLauncher.launch("movement_${name}_${session.id.take(8)}.zip")
                    }
                    showDatasetLabelConfirmation = false
                }) { Text("Confirm label and choose file") }
            },
            dismissButton = {
                TextButton(onClick = { showDatasetLabelConfirmation = false }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun DeviceScreen(
    state: app.vitapulse.android.feature.device.MovementDeviceUiState,
    showDiagnostics: Boolean,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onTest: () -> Unit,
    onRegister: () -> Unit,
    onDiagnostics: () -> Unit,
    onSignIn: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Column {
            Text("Movement device", style = MaterialTheme.typography.headlineMedium)
            Text("ESP32 + MPU6050 · local HTTP connection")
        }
        Card(colors = CardDefaults.cardColors(containerColor = Color.White)) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("ESP32-001", style = MaterialTheme.typography.titleLarge)
                Text("MPU6050 · ${state.connectionState.label()}")
                Text("IP  192.168.4.1")
                Text("Transport  HTTP · polling 100 ms")
                Text("Approx. acquisition  ${state.diagnostics.measuredRateHz?.let { "~${"%.1f".format(Locale.US, it)} Hz" } ?: "measuring after samples"}")
                if (state.connectionState == MovementConnectionState.SENSOR_CONNECTED) {
                    Text("Internet ${if (state.internetAvailable) "available" else "unavailable — local sensor remains connected"}")
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (state.connectionState in setOf(MovementConnectionState.SENSOR_CONNECTED, MovementConnectionState.DEVICE_REACHABLE)) {
                        OutlinedButton(onClick = onDisconnect, enabled = !state.busy) { Text("Disconnect") }
                    } else {
                        Button(onClick = onConnect, enabled = !state.busy) { Text("Connect device") }
                    }
                    OutlinedButton(
                        onClick = onTest,
                        enabled = !state.busy && state.connectionState == MovementConnectionState.SENSOR_CONNECTED &&
                            state.session?.status !in setOf("CALIBRATING", "ACTIVE"),
                    ) {
                        Text("Test connection")
                    }
                }
                if (state.busy) CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
            }
        }
        if (state.connectionState == MovementConnectionState.SENSOR_CONNECTED) {
            state.lastSample?.let { SensorReadout(it, title = "LIVE SENSOR") }
            if (state.signedIn && state.registeredDeviceId == null) {
                Button(onClick = onRegister, enabled = !state.busy) { Text("Register device to account") }
            } else if (!state.signedIn) {
                OutlinedButton(onClick = onSignIn) { Text("Sign in to register and sync") }
            } else {
                Text("Device registered · ${state.registeredDeviceId}")
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onDiagnostics) { Text(if (showDiagnostics) "Hide diagnostics" else "Diagnostics") }
            OutlinedButton(
                onClick = onTest,
                enabled = !state.busy && state.connectionState == MovementConnectionState.SENSOR_CONNECTED &&
                    state.session?.status !in setOf("CALIBRATING", "ACTIVE"),
            ) {
                Text("Run diagnostic")
            }
        }
        if (showDiagnostics) DiagnosticsScreen(state)
    }
}

@Composable
private fun RehabScreen(
    state: app.vitapulse.android.feature.device.MovementDeviceUiState,
    onLoadExercises: () -> Unit,
    onStart: (ExerciseRecord, String) -> Unit,
    onPause: () -> Unit,
    onResume: () -> Unit,
    onEnd: () -> Unit,
) {
    var selectedExercise by remember(state.exercises) { mutableStateOf(state.exercises.firstOrNull()) }
    var selectedPlacement by remember { mutableStateOf("THIGH") }
    var exerciseMenuExpanded by remember { mutableStateOf(false) }
    var placementMenuExpanded by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Column {
            Text("Rehabilitation", style = MaterialTheme.typography.headlineMedium)
            Text("A verified LIVE SENSOR session uses only the connected MPU6050.")
        }
        val session = state.session
        if (session == null || session.status in setOf("COMPLETED", "CALIBRATION_FAILED")) {
            Card(colors = CardDefaults.cardColors(containerColor = Color.White)) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Start live sensor session", style = MaterialTheme.typography.titleLarge)
                    if (state.exercises.isNotEmpty()) {
                        Box {
                            OutlinedButton(
                                modifier = Modifier.fillMaxWidth(),
                                onClick = { exerciseMenuExpanded = true },
                            ) {
                                Text("Assigned exercise: ${selectedExercise?.name ?: "Choose an exercise"}")
                            }
                            DropdownMenu(
                                expanded = exerciseMenuExpanded,
                                onDismissRequest = { exerciseMenuExpanded = false },
                            ) {
                                state.exercises.forEach { exercise ->
                                    DropdownMenuItem(
                                        text = { Text(exercise.name) },
                                        onClick = {
                                            selectedExercise = exercise
                                            exerciseMenuExpanded = false
                                        },
                                    )
                                }
                            }
                        }
                    } else {
                        Text("Sign in to load the assigned exercise list. Offline sensor data can still be tested locally.")
                        if (state.signedIn) OutlinedButton(onClick = onLoadExercises) { Text("Load assigned exercises") }
                        OutlinedButton(
                            onClick = { selectedExercise = ExerciseRecord("", "Local sensor-only check", 10) },
                        ) {
                            Text("Use local sensor-only check")
                        }
                        if (selectedExercise?.id.isNullOrBlank()) {
                            Text("This check is not assigned to Rehab and stays on this device.")
                        }
                    }
                    Text("Sensor placement affects interpretation. Choose the actual attached location.")
                    Box {
                        OutlinedButton(
                            modifier = Modifier.fillMaxWidth(),
                            onClick = { placementMenuExpanded = true },
                        ) {
                            Text("Sensor placement: ${selectedPlacement.replace('_', ' ')}")
                        }
                        DropdownMenu(
                            expanded = placementMenuExpanded,
                            onDismissRequest = { placementMenuExpanded = false },
                        ) {
                            listOf("THIGH", "SHANK", "FOREARM", "UPPER_ARM", "WAIST", "CHEST", "OTHER").forEach { placement ->
                                DropdownMenuItem(
                                    text = { Text(placement.replace('_', ' ')) },
                                    onClick = {
                                        selectedPlacement = placement
                                        placementMenuExpanded = false
                                    },
                                )
                            }
                        }
                    }
                    Button(
                        enabled = state.connectionState == MovementConnectionState.SENSOR_CONNECTED &&
                            !state.busy && selectedExercise != null,
                        onClick = { selectedExercise?.let { onStart(it, selectedPlacement) } },
                    ) {
                        Text(if (selectedExercise?.id.isNullOrBlank()) "Start local check · Calibrate" else "Select exercise · Calibrate")
                    }
                    Text("Calibration collects a stationary session baseline; it is not permanent sensor calibration.")
                }
            }
        } else {
            Card(colors = CardDefaults.cardColors(containerColor = Color.White)) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(session.exerciseName, style = MaterialTheme.typography.titleLarge)
                    Text("LIVE SENSOR · ESP32-001 · MPU6050")
                    Text("Source: LIVE_SENSOR · ${session.placement} · HTTP polling")
                    if (session.status == "CALIBRATING") {
                        Text("SESSION CALIBRATION · keep the sensor still.")
                        CircularProgressIndicator()
                    } else {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("${session.analysis.repetitionCount} / ${session.targetRepetitions} reps")
                            Text("${session.sampleCount} samples")
                        }
                        Text("Movement quality  ${session.analysis.movementQuality}")
                        Text("Stability  ${session.analysis.stability} · smoothness  ${session.analysis.smoothness}")
                        Text("Consistency  ${session.analysis.consistency}")
                        Text("Fatigue signal  ${session.analysis.fatigueSignal}")
                        Text("Sensor quality  ${session.analysis.sensorQuality}")
                        if (session.analysis.recognition == "RECOGNIZED") {
                            Text("Exercise recognition  Detected")
                        } else {
                            Text("Exercise recognition is unavailable for this movement model. The selected Rehab exercise is session context, not an automatic recognition.")
                        }
                        MovementBaselineSummary(session)
                        if (session.anomalies.isNotEmpty()) {
                            Text("Repeated unusual movement pattern detected · review recommended")
                        }
                        RepByRepSummary(session.repetitions.map { it.number to it.quality.name })
                        Text(if (session.status == "ACTIVE") "● Movement sensor connected" else "⚠ ${session.error ?: "Session paused"}")
                        SensorGraph(state.graphSamples)
                        state.lastSample?.let { SensorReadout(it, title = "LIVE SENSOR · reception timestamp") }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (session.status == "ACTIVE") OutlinedButton(onClick = onPause) { Text("Pause") }
                            else OutlinedButton(onClick = onResume) { Text("Resume") }
                            Button(onClick = onEnd) { Text("End session") }
                        }
                        Text("Movement intelligence is based on sensor-derived signals and is not a medical diagnosis.")
                    }

                }
            }
        }
        if (state.localSessions.isNotEmpty()) {
            Text("Local session history", style = MaterialTheme.typography.titleLarge)
            state.localSessions.take(5).forEach { record ->
                Text("${record.exerciseName} · ${record.source} · ${record.syncState} · ${record.sampleCount} samples")
            }
        }
    }
}

@Composable
private fun MovementBaselineSummary(session: app.vitapulse.android.feature.device.LiveSessionUi) {
    if (session.baseline != null) {
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Personal baseline available")
            Text("Current comparison  ${session.baselineComparison}")
            Text(
                "Based on ${session.baseline.sessionCount} sessions and " +
                    "${session.baseline.repetitionCount} valid repetitions.",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    } else {
        Text("Personal baseline not available yet · ${session.baselineComparison}")
    }
}

@Composable
private fun RepByRepSummary(repetitions: List<Pair<Int, String>>) {
    if (repetitions.isEmpty()) return
    Text("Rep-by-rep", style = MaterialTheme.typography.titleMedium)
    repetitions.takeLast(10).forEach { (number, quality) ->
        Text("Rep $number  ${quality.replace('_', ' ').lowercase().replaceFirstChar { it.uppercase() }}")
    }
}

@Composable
private fun DiagnosticsScreen(state: app.vitapulse.android.feature.device.MovementDeviceUiState) {
    val metrics = state.diagnostics
    Card(colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Connection diagnostics", style = MaterialTheme.typography.titleLarge)
            Text("Device  ESP32-001 · IP 192.168.4.1")
            Text("Wi-Fi  ${state.connectionState.label()} · HTTP server  ${if (state.lastSample != null) "REACHABLE" else "UNVERIFIED"}")
            Text("MPU6050  ${if (state.connectionState == MovementConnectionState.SENSOR_CONNECTED) "CONNECTED" else "UNVERIFIED"}")
            Text("Successful requests  ${metrics.successfulRequests}")
            Text("Failed requests  ${metrics.failedRequests} · timeouts ${metrics.timeouts}")
            Text("Invalid samples  ${metrics.invalidSamples} · stale readings ${metrics.staleReadings}")
            Text("Average latency  ${metrics.averageLatencyMs?.let { "%.1f ms".format(Locale.US, it) } ?: "—"}")
            Text("Maximum latency  ${metrics.maxLatencyMs} ms")
            Text("Measured sampling  ${metrics.measuredRateHz?.let { "%.1f Hz".format(Locale.US, it) } ?: "not enough samples"}")
            Text("Internet  ${if (state.internetAvailable) "available" else "unavailable"} · Session ${state.session?.status ?: "INACTIVE"}")
            metrics.lastError?.let { Text("Last error  $it") }
        }
    }
}

@Composable
private fun SensorReadout(sample: MovementSample, title: String) {
    Card(colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = Color(0xFF236C5D))
            Text("Accelerometer · g")
            Text("X ${axis(sample.ax)} g    Y ${axis(sample.ay)} g    Z ${axis(sample.az)} g")
            Text("Gyroscope · °/s")
            Text("X ${axis(sample.gx)} °/s    Y ${axis(sample.gy)} °/s    Z ${axis(sample.gz)} °/s")
            Text("Acceleration magnitude ${"%.3f".format(Locale.US, sample.accelerationMagnitude)} g")
            Text("Gyroscope magnitude ${"%.2f".format(Locale.US, sample.gyroscopeMagnitude)} °/s")
            Text("Received locally at ${sample.appTimestamp} ms")
        }
    }
}

@Composable
private fun SensorGraph(samples: List<MovementSample>) {
    Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFF9FBFA))) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Acceleration and gyroscope magnitude · bounded live window")
            Canvas(Modifier.fillMaxWidth().height(112.dp)) {
                drawLine(Color.LightGray, Offset(0f, size.height / 2), Offset(size.width, size.height / 2))
                if (samples.size > 1) {
                    val maxAcceleration = maxOf(2.0, samples.maxOf { it.accelerationMagnitude })
                    val maxGyroscope = maxOf(250.0, samples.maxOf { it.gyroscopeMagnitude })
                    val accelPath = Path()
                    val gyroPath = Path()
                    samples.forEachIndexed { index, sample ->
                        val x = size.width * index.toFloat() / (samples.size - 1).toFloat()
                        val accelY = size.height * (1.0 - sample.accelerationMagnitude / maxAcceleration).toFloat()
                        val gyroY = size.height * (1.0 - sample.gyroscopeMagnitude / maxGyroscope).toFloat()
                        if (index == 0) {
                            accelPath.moveTo(x, accelY)
                            gyroPath.moveTo(x, gyroY)
                        } else {
                            accelPath.lineTo(x, accelY)
                            gyroPath.lineTo(x, gyroY)
                        }
                    }
                    drawPath(accelPath, Color(0xFF2C7A6B), style = Stroke(width = 3f))
                    drawPath(gyroPath, Color(0xFF6572A5), style = Stroke(width = 2f))
                }
            }
            Text("Green acceleration (g) · blue gyroscope (°/s) · reception-based sampling")
        }
    }
}

@Composable
private fun SignInDialog(onDismiss: () -> Unit, onSignIn: (String, String) -> Unit) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Sign in to VitaPulse") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(email, { email = it }, label = { Text("Email") }, singleLine = true)
                OutlinedTextField(
                    password,
                    { password = it },
                    label = { Text("Password") },
                    visualTransformation = PasswordVisualTransformation(),
                    singleLine = true,
                )
                Text("Credentials are sent to configured Supabase Auth; no password is stored by the app.")
            }
        },
        confirmButton = { Button(onClick = { onSignIn(email.trim(), password) }) { Text("Sign in") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun NoticeCard(message: String, isError: Boolean) {
    Card(colors = CardDefaults.cardColors(containerColor = if (isError) Color(0xFFFFF0EE) else Color(0xFFE8F4F0))) {
        Text(message, Modifier.fillMaxWidth().padding(14.dp), color = if (isError) Color(0xFF8D2E26) else Color(0xFF24584D))
    }
}

private fun axis(value: Double): String = "%+.3f".format(Locale.US, value)

private fun MovementConnectionState.label(): String = when (this) {
    MovementConnectionState.DISCONNECTED -> "Not connected"
    MovementConnectionState.REQUESTING_WIFI -> "Requesting Wi-Fi"
    MovementConnectionState.CONNECTING -> "Verifying"
    MovementConnectionState.CONNECTED -> "Wi-Fi connected"
    MovementConnectionState.DEVICE_REACHABLE -> "ESP32 reachable"
    MovementConnectionState.SENSOR_CONNECTED -> "CONNECTED"
    MovementConnectionState.DEGRADED -> "Connection degraded"
    MovementConnectionState.RECONNECTING -> "Reconnecting"
    MovementConnectionState.NETWORK_PERMISSION_REQUIRED -> "Local-network permission required"
    MovementConnectionState.WIFI_CONNECTION_FAILED -> "Wi-Fi connection failed"
    MovementConnectionState.DEVICE_UNREACHABLE -> "ESP32 unreachable"
    MovementConnectionState.SENSOR_UNAVAILABLE -> "MPU6050 unavailable"
    MovementConnectionState.ERROR -> "Device error"
    MovementConnectionState.SIMULATION -> "Simulation"
}
