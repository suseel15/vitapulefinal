package app.vitapulse.android.feature.wellbeing

import android.Manifest
import android.os.Build
import android.content.Context
import android.content.ContextWrapper
import android.content.pm.PackageManager
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.ViewGroup
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import app.vitapulse.android.VitaPulseApplication
import app.vitapulse.android.feature.wellbeing.analysis.CameraWellbeingFeatureExtractor
import app.vitapulse.android.feature.wellbeing.analysis.FacePrecheck
import app.vitapulse.android.feature.wellbeing.analysis.FrameObservation
import app.vitapulse.android.feature.wellbeing.camera.CameraController
import app.vitapulse.android.feature.wellbeing.data.CameraWellbeingSessionEntity
import app.vitapulse.android.feature.wellbeing.data.SleepRecordEntity
import app.vitapulse.android.feature.wellbeing.data.WellbeingCheckInEntity
import app.vitapulse.android.feature.wellbeing.domain.WellbeingTrendAnalyzer
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlinx.coroutines.delay

@Composable
fun WellbeingFeatureScreen(
    modifier: Modifier = Modifier,
    onOpenConnect: () -> Unit = {},
) {
    val context = LocalContext.current
    val model: WellbeingViewModel = viewModel(
        factory = WellbeingViewModel.create(context.applicationContext as VitaPulseApplication),
    )
    val state by model.state.collectAsStateWithLifecycle()
    var route by remember { mutableStateOf("wellbeing") }
    var cameraPermissionRequested by remember {
        mutableStateOf(context.getSharedPreferences("vitapulse-wellbeing", Context.MODE_PRIVATE)
            .getBoolean("camera_permission_requested", false))
    }
    var cameraEnabled by remember {
        mutableStateOf(context.getSharedPreferences("vitapulse-wellbeing", Context.MODE_PRIVATE)
            .getBoolean("camera_enabled", true))
    }
    var storeCameraHistory by remember {
        mutableStateOf(context.getSharedPreferences("vitapulse-wellbeing", Context.MODE_PRIVATE)
            .getBoolean("store_camera_history", true))
    }
    val hasCameraPermission = ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
        PackageManager.PERMISSION_GRANTED
    val lifecycleOwner = LocalLifecycleOwner.current
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        cameraPermissionRequested = true
        context.getSharedPreferences("vitapulse-wellbeing", Context.MODE_PRIVATE)
            .edit().putBoolean("camera_permission_requested", true).apply()
        route = if (granted) "camera_precheck" else "camera_permission"
    }

    BackHandler(enabled = route != "wellbeing") { route = "wellbeing" }

    DisposableEffect(lifecycleOwner, route) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME &&
                route == "camera-permission" &&
                ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
            ) {
                route = "camera_precheck"
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    if (route in setOf("camera_precheck", "camera_session")) {
        CameraFlowScreen(
            modifier = modifier,
            onCancel = { route = "wellbeing" },
            onComplete = { startedAt, observations, duration ->
                model.saveCameraAssessment(startedAt, observations, duration, storeCameraHistory) {
                    route = "camera_result"
                }
            },
        )
        return
    }

    LazyColumn(
        modifier = modifier.fillMaxSize().padding(horizontal = 18.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                if (route != "wellbeing") {
                    TextButton(onClick = { route = "wellbeing" }) { Text("← Back") }
                }
                Text(
                    when (route) {
                        "wellbeing" -> "Wellbeing"
                        "check-in" -> "Daily Check-In"
                        "camera-intro" -> "30-Second Camera Check"
                        "camera-permission" -> "Camera access"
                        "camera-result" -> "Camera observations"
                        "sleep" -> "Sleep"
                        "recovery" -> "Recovery"
                        "history" -> "Wellbeing history"
                        "trends" -> "Wellbeing trends"
                        "reports" -> "Wellbeing reports"
                        "privacy" -> "Wellbeing privacy"
                        else -> "Wellbeing"
                    },
                    style = MaterialTheme.typography.headlineMedium,
                )
                state.error?.let { MessageCard(it, error = true) }
                state.notice?.let { MessageCard(it, error = false) }
            }
        }
        when (route) {
            "wellbeing" -> {
                item {
                    app.vitapulse.android.feature.connect.ConnectedHealthContextCard(
                        title = "Connected recovery data",
                        onOpenConnect = onOpenConnect,
                    )
                }
                item {
                    WellbeingHub(
                        checkIn = state.checkIns.firstOrNull()?.takeIf { isToday(it.createdAtMs) },
                        latestCamera = state.cameraSessions.firstOrNull(),
                        latestSleep = state.sleepRecords.firstOrNull(),
                        latestRecovery = state.recoveryRecords.firstOrNull(),
                        cameraEnabled = cameraEnabled,
                        syncState = state.syncState,
                        onRoute = { route = it },
                        onSync = model::syncPending,
                    )
                }
            }
            "check-in" -> item { CheckInForm(onSave = model::saveCheckIn, onDone = { route = "wellbeing" }) }
            "camera-intro" -> item {
                CameraIntroduction(
                    cameraEnabled = cameraEnabled,
                    onContinue = {
                        if (hasCameraPermission) {
                            route = "camera_precheck"
                        } else {
                            route = "camera-permission"
                        }
                    },
                    onNotNow = { route = "wellbeing" },
                )
            }
            "camera-permission" -> item {
                CameraPermissionScreen(
                    context = context,
                    requestedBefore = cameraPermissionRequested,
                    onRequest = { permissionLauncher.launch(Manifest.permission.CAMERA) },
                    onTryAgain = {
                        context.startActivity(
                            Intent(
                                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.fromParts("package", context.packageName, null),
                            ),
                        )
                    },
                    onContinueWithout = { route = "wellbeing" },
                )
            }
            "camera-result" -> item {
                CameraResultScreen(
                    state.cameraSessions.firstOrNull(),
                    state.cameraFeatures.firstOrNull(),
                    state.latestCameraPreview,
                )
            }
            "sleep" -> item {
                SleepScreen(
                    sleep = state.sleepRecords.firstOrNull(),
                    onSave = model::saveSleep,
                )
            }
            "recovery" -> item {
                RecoveryScreen(
                    record = state.recoveryRecords.firstOrNull(),
                    checkIn = state.checkIns.firstOrNull(),
                    sleep = state.sleepRecords.firstOrNull(),
                    onCalculate = model::saveRecovery,
                )
            }
            "history" -> item { WellbeingHistory(state) }
            "trends" -> item { WellbeingTrends(state) }
            "reports" -> item {
                WellbeingReports(state, onGenerate = model::generateReport)
            }
            "privacy" -> item {
                PrivacyScreen(
                    cameraEnabled = cameraEnabled,
                    storeCameraHistory = storeCameraHistory,
                    onCameraEnabled = {
                        cameraEnabled = it
                        context.getSharedPreferences("vitapulse-wellbeing", Context.MODE_PRIVATE)
                            .edit().putBoolean("camera_enabled", it).apply()
                    },
                    onStoreCameraHistory = {
                        storeCameraHistory = it
                        context.getSharedPreferences("vitapulse-wellbeing", Context.MODE_PRIVATE)
                            .edit().putBoolean("store_camera_history", it).apply()
                    },
                )
            }
        }
        item { Spacer(Modifier.height(20.dp)) }
    }
}

@Composable
private fun WellbeingHub(
    checkIn: WellbeingCheckInEntity?,
    latestCamera: CameraWellbeingSessionEntity?,
    latestSleep: SleepRecordEntity?,
    latestRecovery: app.vitapulse.android.feature.wellbeing.data.RecoveryRecordEntity?,
    cameraEnabled: Boolean,
    syncState: String,
    onRoute: (String) -> Unit,
    onSync: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("How are you feeling today? How well are you recovering?")
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Today's Wellbeing", style = MaterialTheme.typography.titleLarge)
                MetricRow("Energy", checkIn?.energy?.let { scaleLabel(it, "positive") }, "SELF_REPORTED".takeIf { checkIn != null })
                MetricRow("Stress", checkIn?.stress?.let { scaleLabel(it, "negative") }, "SELF_REPORTED".takeIf { checkIn != null })
                MetricRow("Fatigue", checkIn?.fatigue?.let { scaleLabel(it, "negative") }, "SELF_REPORTED".takeIf { checkIn != null })
                MetricRow("Soreness", checkIn?.soreness?.let { scaleLabel(it, "negative") }, "SELF_REPORTED".takeIf { checkIn != null })
                MetricRow("Recovery feeling", checkIn?.recoveryFeeling?.let { scaleLabel(it, "positive") }, "SELF_REPORTED".takeIf { checkIn != null })
                if (checkIn == null) Text("Not recorded yet")
                Button(onClick = { onRoute("check-in") }, modifier = Modifier.fillMaxWidth()) {
                    Text("Daily Check-In")
                }
            }
        }
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("30-Second Camera Check", style = MaterialTheme.typography.titleLarge)
                Text("Observe face presence and movement features during a short guided session.")
                Text("Camera observations are not a medical or mental-health diagnosis.")
                if (latestCamera != null) {
                    MetricRow("Last capture quality", latestCamera.captureQuality, "CAMERA_OBSERVED")
                } else {
                    Text("Not recorded")
                }
                Button(
                    onClick = { onRoute("camera-intro") },
                    enabled = cameraEnabled,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (cameraEnabled) "Start Camera Check" else "Camera Check Disabled")
                }
            }
        }
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Recovery", style = MaterialTheme.typography.titleLarge)
                Text(latestRecovery?.recoveryState ?: "Not recorded")
                Text("Based only on available supporting information; no unexplained combined score.")
                OutlinedButton(onClick = { onRoute("recovery") }) { Text("View Recovery") }
            }
        }
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Sleep", style = MaterialTheme.typography.titleLarge)
                Text(latestSleep?.let { durationLabel(it.durationMinutes) } ?: "Not recorded")
                Text(latestSleep?.source?.replace('_', ' ') ?: "Source —")
                OutlinedButton(onClick = { onRoute("sleep") }) { Text("Sleep Details") }
            }
        }
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Your wellbeing", style = MaterialTheme.typography.titleLarge)
                OutlinedButton(onClick = { onRoute("trends") }, modifier = Modifier.fillMaxWidth()) { Text("Trends") }
                OutlinedButton(onClick = { onRoute("history") }, modifier = Modifier.fillMaxWidth()) { Text("History") }
                OutlinedButton(onClick = { onRoute("reports") }, modifier = Modifier.fillMaxWidth()) { Text("Reports") }
                OutlinedButton(onClick = { onRoute("privacy") }, modifier = Modifier.fillMaxWidth()) { Text("Privacy Settings") }
            }
        }
        WhiteCard {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column {
                    Text("Data sync", style = MaterialTheme.typography.titleMedium)
                    Text(syncState.replace('_', ' '))
                }
                OutlinedButton(onClick = onSync) { Text("Sync now") }
            }
        }
    }
}

@Composable
private fun CheckInForm(onSave: (Int, Int, Int, Int, Int, String) -> Unit, onDone: () -> Unit) {
    var energy by remember { mutableIntStateOf(0) }
    var stress by remember { mutableIntStateOf(0) }
    var fatigue by remember { mutableIntStateOf(0) }
    var soreness by remember { mutableIntStateOf(0) }
    var recovery by remember { mutableIntStateOf(0) }
    var note by remember { mutableStateOf("") }
    var saved by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Your responses are self-reported and are not a diagnosis.")
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                RatingScale("How is your energy today?", energy) { energy = it }
                RatingScale("How stressed do you feel?", stress) { stress = it }
                RatingScale("How fatigued do you feel?", fatigue) { fatigue = it }
                RatingScale("How sore do you feel?", soreness) { soreness = it }
                RatingScale("How recovered do you feel?", recovery) { recovery = it }
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it.take(MAX_WELLBEING_NOTE_LENGTH) },
                    label = { Text("Anything else you want to record? (optional)") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 2,
                    supportingText = { Text("${note.length}/$MAX_WELLBEING_NOTE_LENGTH") },
                )
                Button(
                    onClick = {
                        onSave(energy, stress, fatigue, soreness, recovery, note)
                        saved = true
                    },
                    enabled = listOf(energy, stress, fatigue, soreness, recovery).all { it in 1..5 },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Save Check-In") }
            }
        }
        if (saved) {
            WhiteCard {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Check-In Saved", style = MaterialTheme.typography.titleLarge)
                    Text("Your wellbeing check-in has been recorded as a self-report.")
                    OutlinedButton(onClick = onDone) { Text("Done") }
                }
            }
        }
    }
}

@Composable
private fun RatingScale(title: String, selected: Int, onSelect: (Int) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            (1..5).forEach { value ->
                FilterChip(
                    selected = selected == value,
                    onClick = { onSelect(value) },
                    label = { Text(value.toString()) },
                )
            }
        }
        Text(
            when (title) {
                "How is your energy today?" -> "1 Very Low · 2 Low · 3 Moderate · 4 Good · 5 Excellent"
                "How stressed do you feel?" -> "1 Very Low · 2 Low · 3 Moderate · 4 High · 5 Very High"
                else -> "1 Very Low · 2 Low · 3 Moderate · 4 Good · 5 Excellent"
            },
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun CameraIntroduction(cameraEnabled: Boolean, onContinue: () -> Unit, onNotNow: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("A short guided camera session observes basic facial and movement characteristics that may contribute to wellbeing context.")
                Text("This is not a medical or mental-health diagnosis.")
                Text("The camera is active only during the assessment.")
                Text("Raw video is not stored or uploaded. Face identity recognition is not performed.")
                Text("Camera permission is requested only when you continue.")
            }
        }
        Button(onClick = onContinue, enabled = cameraEnabled, modifier = Modifier.fillMaxWidth()) {
            Text("Continue")
        }
        OutlinedButton(onClick = onNotNow, modifier = Modifier.fillMaxWidth()) { Text("Not Now") }
    }
}

@Composable
private fun CameraPermissionScreen(
    context: Context,
    requestedBefore: Boolean,
    onRequest: () -> Unit,
    onTryAgain: () -> Unit,
    onContinueWithout: () -> Unit,
) {
    val activity = context.findActivity()
    val rationale = activity?.let {
        androidx.core.app.ActivityCompat.shouldShowRequestPermissionRationale(it, Manifest.permission.CAMERA)
    } ?: false
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Camera access unavailable", style = MaterialTheme.typography.titleLarge)
                Text("You can continue using Wellbeing without the camera assessment.")
                Text(
                    when {
                        rationale -> "Camera access is needed only to observe the guided 30-second session."
                        requestedBefore -> "Camera permission was denied. Enable it in Android app settings to try again."
                        else -> "Allow camera access when prompted to continue with this optional check."
                    },
                )
            }
        }
        Button(onClick = if (requestedBefore && !rationale) onTryAgain else onRequest, modifier = Modifier.fillMaxWidth()) {
            Text(if (requestedBefore && !rationale) "Open Settings to Try Again" else "Try Again")
        }
        OutlinedButton(onClick = onContinueWithout, modifier = Modifier.fillMaxWidth()) {
            Text("Continue Without Camera")
        }
    }
}

@Composable
private fun CameraFlowScreen(
    modifier: Modifier = Modifier,
    onCancel: () -> Unit,
    onComplete: (Long, List<FrameObservation>, Int) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val handler = remember { Handler(Looper.getMainLooper()) }
    val observations = remember { mutableStateListOf<FrameObservation>() }
    var latestCheck by remember { mutableStateOf<FacePrecheck?>(null) }
    var active by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var secondsRemaining by remember { mutableIntStateOf(30) }
    var sessionStartAtMs by remember { mutableStateOf<Long?>(null) }
    var sessionStartedElapsedMs by remember { mutableStateOf<Long?>(null) }
    var faceStatus by remember { mutableStateOf<FacePrecheck?>(null) }
    val controller = remember(context, lifecycleOwner) {
        CameraController(
            context,
            lifecycleOwner,
            onObservation = { observation ->
                handler.post {
                    latestCheck = CameraWellbeingFeatureExtractor.precheck(observation)
                    faceStatus = latestCheck
                    if (active && observations.size < MAX_SESSION_OBSERVATIONS) observations.add(observation)
                }
            },
            onFailure = { failure -> handler.post { error = failure.message ?: "Camera is unavailable." } },
        )
    }
    var previewView by remember { mutableStateOf<PreviewView?>(null) }
    DisposableEffect(controller) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP && active) {
                controller.close()
                onCancel()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            controller.close()
        }
    }
    LaunchedEffect(previewView) {
        previewView?.let(controller::start)
    }
    LaunchedEffect(active, sessionStartedElapsedMs) {
        val started = sessionStartedElapsedMs ?: return@LaunchedEffect
        while (active) {
            val elapsed = (android.os.SystemClock.elapsedRealtime() - started).coerceAtLeast(0)
            val remaining = ((30_000L - elapsed + 999L) / 1_000L).toInt().coerceAtLeast(0)
            secondsRemaining = remaining
            if (remaining == 0) {
                active = false
                controller.close()
                onComplete(sessionStartAtMs ?: System.currentTimeMillis(), observations.toList(), 30)
                break
            }
            delay(200)
        }
    }

    Column(modifier = modifier.padding(horizontal = 18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("30-SECOND CAMERA CHECK", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text("Keep your face inside the guide. Camera-observed features are not diagnoses.")
        Box(
            modifier = Modifier.fillMaxWidth().height(320.dp).background(
                MaterialTheme.colorScheme.surfaceVariant,
                RoundedCornerShape(20.dp),
            ),
            contentAlignment = Alignment.Center,
        ) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { viewContext ->
                    PreviewView(viewContext).also {
                        it.layoutParams = ViewGroup.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT,
                        )
                        it.scaleType = PreviewView.ScaleType.FILL_CENTER
                        previewView = it
                    }
                },
            )
            Box(
                modifier = Modifier.size(width = 220.dp, height = 270.dp)
                    .background(androidx.compose.ui.graphics.Color.Transparent, RoundedCornerShape(120.dp)),
            )
            Canvas(Modifier.size(width = 220.dp, height = 270.dp)) {
                drawOval(
                    color = Color.White,
                    style = Stroke(width = 4.dp.toPx()),
                )
            }
        }
        Text(
            when (faceStatus) {
                FacePrecheck.NO_FACE -> "No face detected. Move into the frame."
                FacePrecheck.MULTIPLE_FACES -> "Multiple faces detected. Please make sure only you are in the frame."
                FacePrecheck.FACE_TOO_SMALL -> "Move closer to the camera."
                FacePrecheck.FACE_OFF_CENTER -> "Move your face toward the center of the frame."
                FacePrecheck.POOR_LIGHTING -> "Move to a well-lit area."
                FacePrecheck.BLURRY -> "Hold the phone steady and let the camera focus."
                FacePrecheck.FACE_NOT_FACING_CAMERA -> "Face the camera."
                FacePrecheck.READY -> if (active) "Keep your face inside the frame." else "Face is in position. Keep the phone steady."
                null -> "Position your face inside the frame. Keep your phone steady in a well-lit area."
            },
        )
        if (active) {
            Text("$secondsRemaining sec", style = MaterialTheme.typography.displaySmall)
            LinearProgressIndicator(
                progress = { (30 - secondsRemaining) / 30f },
                modifier = Modifier.fillMaxWidth(),
            )
            TextButton(onClick = {
                val started = sessionStartedElapsedMs ?: return@TextButton
                val elapsed = ((android.os.SystemClock.elapsedRealtime() - started) / 1_000).toInt().coerceIn(0, 29)
                active = false
                controller.close()
                onComplete(sessionStartAtMs ?: System.currentTimeMillis(), observations.toList(), elapsed)
            }) { Text("Stop and save incomplete capture") }
        } else if (latestCheck == FacePrecheck.READY && error == null) {
            Button(onClick = {
                observations.clear()
                sessionStartAtMs = System.currentTimeMillis()
                sessionStartedElapsedMs = android.os.SystemClock.elapsedRealtime()
                secondsRemaining = 30
                active = true
            }, modifier = Modifier.fillMaxWidth()) {
                Text("Start 30-Second Check")
            }
        }
        error?.let { MessageCard("Camera unavailable: $it", error = true) }
        OutlinedButton(onClick = {
            active = false
            controller.close()
            onCancel()
        }, modifier = Modifier.fillMaxWidth()) { Text("Cancel") }
    }
}

@Composable
private fun CameraResultScreen(
    session: CameraWellbeingSessionEntity?,
    feature: app.vitapulse.android.feature.wellbeing.data.CameraWellbeingFeatureEntity?,
    preview: app.vitapulse.android.feature.wellbeing.analysis.CameraWellbeingFeatures?,
) {
    if (session == null && preview == null) {
        WhiteCard { Text("No camera result is available yet.") }
        return
    }
    val quality = preview?.captureQuality ?: session?.captureQuality ?: "INSUFFICIENT_DATA"
    val facePresenceRatio = preview?.facePresenceRatio ?: session?.facePresenceRatio ?: 0.0
    val movementMagnitude = preview?.headMovementMagnitude ?: feature?.headMovementMagnitude
    val positionStability = preview?.facePositionStability ?: feature?.facePositionStability
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("30-Second Camera Check", style = MaterialTheme.typography.titleLarge)
                MetricRow("Capture quality", quality, "CAMERA_OBSERVED")
                MetricRow(
                    "Face presence",
                    if (facePresenceRatio >= 0.8) "Stable" else "Variable",
                    "CAMERA_OBSERVED",
                )
                MetricRow("Head movement", movementMagnitude?.let(::movementLevel), "CAMERA_OBSERVED")
                MetricRow("Visual consistency", positionStability, "CAMERA_OBSERVED")
            }
        }
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Camera observations", style = MaterialTheme.typography.titleLarge)
                Text("Face presence: ${"%.0f".format(Locale.US, facePresenceRatio * 100)}% of observed frames")
                (preview?.multipleFaceFrames ?: session?.multipleFaceFrames)?.let { Text("Multiple-face frames: $it") }
                if (preview != null) {
                    Text("Valid frames: ${preview.validFrames} · Invalid frames: ${preview.invalidFrames}")
                    Text("Poor-lighting frames: ${preview.poorLightingFrames} · Face out-of-frame: ${preview.faceOutOfFrameFrames}")
                } else if (feature != null) {
                    Text("Valid frames: ${feature.validFrames} · Invalid frames: ${feature.invalidFrames}")
                    Text("Poor-lighting frames: ${feature.poorLightingFrames} · Face out-of-frame: ${feature.faceOutOfFrameFrames}")
                }
                (if (preview != null) preview.eyeObservationRatio else feature?.eyeObservationRatio)?.let {
                    Text("Eye-region observations were available in ${"%.0f".format(Locale.US, it * 100)}% of frames.")
                }
                (if (preview != null) preview.smileObservationRatio else feature?.smileObservationRatio)?.let {
                    Text("Smile classification observations were available in ${"%.0f".format(Locale.US, it * 100)}% of frames.")
                }
                Text("These are camera-observed features, not a medical or mental-health diagnosis.")
                Text("Raw video was not saved. Face identity recognition was not performed.")
                Text(
                    if (session?.status == "COMPLETED") "Assessment completed."
                    else if (session != null) "Capture quality was insufficient for a completed assessment."
                    else "This result was not saved to camera history.",
                )
            }
        }
    }
}

@Composable
private fun SleepScreen(sleep: SleepRecordEntity?, onSave: (Long, Long, Int?, Int?, String) -> Unit) {
    val zone = remember { ZoneId.systemDefault() }
    var bedtime by remember { mutableStateOf("22:30") }
    var wakeTime by remember { mutableStateOf("06:30") }
    var quality by remember { mutableStateOf("") }
    var interruptions by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Last Night", style = MaterialTheme.typography.titleLarge)
                MetricRow("Duration", sleep?.let { durationLabel(it.durationMinutes) }, sleep?.source)
                MetricRow("Quality", sleep?.qualityRating?.let { scaleLabel(it, "positive") }, sleep?.source)
                MetricRow("Source", sleep?.source?.replace('_', ' '), null)
                if (sleep == null) Text("Not recorded")
            }
        }
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Add a sleep record", style = MaterialTheme.typography.titleLarge)
                Text("Use 24-hour time (HH:mm). Duration is calculated from bedtime and wake time. Sleep stages are not estimated.")
                OutlinedTextField(bedtime, { bedtime = it.take(5) }, label = { Text("Bedtime") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text), singleLine = true)
                OutlinedTextField(wakeTime, { wakeTime = it.take(5) }, label = { Text("Wake time") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text), singleLine = true)
                OutlinedTextField(quality, { quality = it.filter(Char::isDigit).take(1) }, label = { Text("Sleep quality (optional, 1–5)") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), singleLine = true)
                OutlinedTextField(interruptions, { interruptions = it.filter(Char::isDigit).take(3) }, label = { Text("Night interruptions (optional)") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), singleLine = true)
                OutlinedTextField(note, { note = it.take(500) }, label = { Text("Notes (optional)") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                Button(onClick = {
                    try {
                        val today = LocalDate.now()
                        val startTime = LocalTime.parse(bedtime)
                        val endTime = LocalTime.parse(wakeTime)
                        val startDate = if (endTime.isAfter(startTime)) today else today.minusDays(1)
                        val start = startDate.atTime(startTime).atZone(zone).toInstant().toEpochMilli()
                        val end = today.atTime(endTime).atZone(zone).toInstant().toEpochMilli()
                        onSave(start, end, quality.toIntOrNull(), interruptions.toIntOrNull(), note)
                        error = null
                    } catch (_: Exception) {
                        error = "Use valid 24-hour bedtime and wake times."
                    }
                }, modifier = Modifier.fillMaxWidth()) { Text("Save Sleep Entry") }
            }
        }
    }
}

@Composable
private fun RecoveryScreen(
    record: app.vitapulse.android.feature.wellbeing.data.RecoveryRecordEntity?,
    checkIn: WellbeingCheckInEntity?,
    sleep: SleepRecordEntity?,
    onCalculate: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Recovery", style = MaterialTheme.typography.titleLarge)
                Text(record?.recoveryState ?: "INSUFFICIENT_DATA", style = MaterialTheme.typography.headlineSmall)
                Text("Recovery is a category with its supporting factors, not a single unexplained score.")
                Text("Based on: ${record?.supportingFactors?.let(::readableFactors) ?: "No recovery record yet"}")
                record?.let { MetricRow("Source", it.source, "CALCULATED") }
            }
        }
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Available factors")
                MetricRow("Self-reported fatigue", checkIn?.fatigue?.let { scaleLabel(it, "negative") }, "SELF_REPORTED".takeIf { checkIn != null })
                MetricRow("Self-reported soreness", checkIn?.soreness?.let { scaleLabel(it, "negative") }, "SELF_REPORTED".takeIf { checkIn != null })
                MetricRow("Recovery feeling", checkIn?.recoveryFeeling?.let { scaleLabel(it, "positive") }, "SELF_REPORTED".takeIf { checkIn != null })
                MetricRow("Sleep", sleep?.let { durationLabel(it.durationMinutes) }, sleep?.source)
            }
        }
        Button(onClick = onCalculate, modifier = Modifier.fillMaxWidth()) { Text("Update Recovery Context") }
    }
}

@Composable
private fun WellbeingHistory(state: app.vitapulse.android.feature.wellbeing.domain.WellbeingUiState) {
    var typeFilter by remember { mutableStateOf("All") }
    var days by remember { mutableIntStateOf(30) }
    var customRange by remember { mutableStateOf(false) }
    var customFrom by remember { mutableStateOf(LocalDate.now().minusDays(7).toString()) }
    var customTo by remember { mutableStateOf(LocalDate.now().toString()) }
    val startOfCustomRange = remember(customRange, customFrom) {
        if (!customRange) null else runCatching {
            LocalDate.parse(customFrom).atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli()
        }.getOrNull()
    }
    val endOfCustomRange = remember(customRange, customTo) {
        if (!customRange) null else runCatching {
            LocalDate.parse(customTo).plusDays(1).atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli() - 1
        }.getOrNull()
    }
    val rangeValid = !customRange ||
        (startOfCustomRange != null && endOfCustomRange != null && endOfCustomRange >= startOfCustomRange)
    val items = remember(state, typeFilter, days, customRange, startOfCustomRange, endOfCustomRange, rangeValid) {
        val cutoff = System.currentTimeMillis() - days * 24L * 60L * 60L * 1_000L
        buildList {
            state.checkIns.filter { it.createdAtMs >= cutoff }.forEach { add(HistoryRow(it.createdAtMs, "Check-In", "${it.energy}/5 energy · ${it.fatigue}/5 fatigue", it.source)) }
            state.cameraSessions.filter { it.startedAtMs >= cutoff }.forEach { add(HistoryRow(it.startedAtMs, "Camera Check", it.captureQuality, it.source)) }
            state.sleepRecords.filter { it.startAtMs >= cutoff }.forEach { add(HistoryRow(it.startAtMs, "Sleep", durationLabel(it.durationMinutes), it.source)) }
            state.recoveryRecords.filter { it.createdAtMs >= cutoff }.forEach { add(HistoryRow(it.createdAtMs, it.recoveryState, it.recoveryState, it.source)) }
            state.reports.filter { it.createdAtMs >= cutoff }.forEach { add(HistoryRow(it.createdAtMs, "Report", it.reportType.replace('_', ' '), it.sourceProvenance)) }
        }.filter {
            val isInRange = if (customRange) {
                rangeValid && it.timestampMs >= startOfCustomRange!! && it.timestampMs <= endOfCustomRange!!
            } else {
                it.timestampMs >= cutoff
            }
            isInRange && (typeFilter == "All" || it.type.equals(typeFilter, ignoreCase = true))
        }
            .sortedByDescending { it.timestampMs }
    }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            listOf(7, 30, 90).forEach { period ->
                FilterChip(
                    selected = !customRange && days == period,
                    onClick = { days = period; customRange = false },
                    label = { Text("$period days") },
                )
            }
            FilterChip(selected = customRange, onClick = { customRange = true }, label = { Text("Custom") })
        }
        if (customRange) {
            WhiteCard {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Custom date range · use YYYY-MM-DD")
                    OutlinedTextField(customFrom, { customFrom = it.take(10) }, label = { Text("From") }, singleLine = true)
                    OutlinedTextField(customTo, { customTo = it.take(10) }, label = { Text("To") }, singleLine = true)
                    if (!rangeValid) Text("Enter valid dates with the start on or before the end.", color = MaterialTheme.colorScheme.error)
                }
            }
        }
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            listOf("All", "Check-In", "Camera", "Sleep", "Recovery", "Report").forEach { value ->
                FilterChip(selected = typeFilter == value, onClick = { typeFilter = value }, label = { Text(value) })
            }
        }
        if (customRange && !rangeValid) {
            Text("Correct the custom date range to see wellbeing history.")
        } else if (items.isEmpty()) {
            WhiteCard { Text("No wellbeing records in this period. Nothing has been estimated.") }
        } else {
            items.forEach { entry ->
                WhiteCard {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(entry.type, style = MaterialTheme.typography.titleMedium)
                        Text(entry.summary)
                        Text("Source: ${entry.source}")
                        Text(DateTimeFormatter.ofPattern("EEE, MMM d · HH:mm", Locale.getDefault())
                            .withZone(ZoneId.systemDefault()).format(java.time.Instant.ofEpochMilli(entry.timestampMs)))
                    }
                }
            }
        }
    }
}

@Composable
private fun WellbeingTrends(state: app.vitapulse.android.feature.wellbeing.domain.WellbeingUiState) {
    var days by remember { mutableIntStateOf(7) }
    val cutoff = System.currentTimeMillis() - days * 24L * 60L * 60L * 1_000L
    val checkIns = state.checkIns.filter { it.createdAtMs >= cutoff }.sortedBy { it.createdAtMs }
    val sleepRecords = state.sleepRecords.filter { it.startAtMs >= cutoff }.sortedBy { it.startAtMs }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf(7, 30, 90).forEach { period ->
                FilterChip(selected = days == period, onClick = { days = period }, label = { Text("$period days") })
            }
        }
        listOf(
            TrendSeries("Energy", checkIns.map { it.energy.toDouble() }, checkIns.map { it.energy.toDouble() }, "SELF_REPORTED"),
            TrendSeries("Stress", checkIns.map { (6 - it.stress).toDouble() }, checkIns.map { it.stress.toDouble() }, "SELF_REPORTED"),
            TrendSeries("Fatigue", checkIns.map { (6 - it.fatigue).toDouble() }, checkIns.map { it.fatigue.toDouble() }, "SELF_REPORTED"),
            TrendSeries("Soreness", checkIns.map { (6 - it.soreness).toDouble() }, checkIns.map { it.soreness.toDouble() }, "SELF_REPORTED"),
            TrendSeries("Recovery feeling", checkIns.map { it.recoveryFeeling.toDouble() }, checkIns.map { it.recoveryFeeling.toDouble() }, "SELF_REPORTED"),
            TrendSeries(
                "Sleep duration",
                sleepRecords.map { it.durationMinutes.toDouble() },
                sleepRecords.map { it.durationMinutes.toDouble() },
                sleepRecords.map { it.source }.distinct().joinToString().ifBlank { "SELF_REPORTED" },
            ),
            TrendSeries(
                "Camera observation trend",
                state.cameraSessions.filter { it.startedAtMs >= cutoff }.map { it.validFrameRatio * 100 },
                state.cameraSessions.filter { it.startedAtMs >= cutoff }.map { it.validFrameRatio * 100 },
                "CAMERA_OBSERVED · capture quality only",
            ),
        ).forEach { series ->
            val trend = WellbeingTrendAnalyzer.classify(series.trendValues)
            WhiteCard {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(series.name, style = MaterialTheme.typography.titleMedium)
                    Text(if (series.trendValues.isEmpty()) "Trend unavailable" else trend.classification)
                    Text("Observations: ${trend.observationCount} · Source: ${series.source}")
                    if (series.rawValues.isNotEmpty()) Text("Recorded values: ${series.rawValues.joinToString(" · ") { formatValue(it) }}")
                }
            }
        }
        Text("Trends describe recorded observations only; they do not establish causes or diagnoses.")
    }
}

@Composable
private fun WellbeingReports(
    state: app.vitapulse.android.feature.wellbeing.domain.WellbeingUiState,
    onGenerate: (String) -> Unit,
) {
    val reportTypes = listOf(
        "WELLBEING_CHECKIN", "CAMERA_WELLBEING", "SLEEP", "RECOVERY", "WEEKLY_WELLBEING", "MONTHLY_WELLBEING",
    )
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Create a wellbeing report", style = MaterialTheme.typography.titleLarge)
                Text("Reports include available records, explicit source labels, and limitations. Missing data stays missing.")
                reportTypes.forEach { type ->
                    OutlinedButton(onClick = { onGenerate(type) }, modifier = Modifier.fillMaxWidth()) {
                        Text(type.replace('_', ' '))
                    }
                }
            }
        }
        state.reports.forEach { report ->
            WhiteCard {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(report.reportType.replace('_', ' '), style = MaterialTheme.typography.titleMedium)
                    Text("Sources: ${report.sourceProvenance}")
                    Text("Limitations: ${report.limitations}")
                }
            }
        }
        if (state.reports.isEmpty()) Text("No reports recorded.")
    }
}

@Composable
private fun PrivacyScreen(
    cameraEnabled: Boolean,
    storeCameraHistory: Boolean,
    onCameraEnabled: (Boolean) -> Unit,
    onStoreCameraHistory: (Boolean) -> Unit,
) {
    val context = LocalContext.current
    val preferences = remember { context.getSharedPreferences("vitapulse-wellbeing", Context.MODE_PRIVATE) }
    var reminderEnabled by remember {
        mutableStateOf(
            preferences.getBoolean("reminder_enabled", false) &&
                (Build.VERSION.SDK_INT < 33 ||
                    ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
                    PackageManager.PERMISSION_GRANTED),
        )
    }
    LaunchedEffect(Unit) {
        if (preferences.getBoolean("reminder_enabled", false) && !reminderEnabled) {
            WellbeingReminderReceiver.cancel(context)
            preferences.edit().putBoolean("reminder_enabled", false).apply()
        }
    }
    var reminderTime by remember { mutableStateOf(preferences.getString("reminder_time", "19:00") ?: "19:00") }
    var reminderMessage by remember { mutableStateOf<String?>(null) }
    val notificationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            val failure = scheduleWellbeingReminder(context, preferences, reminderTime)
            reminderEnabled = failure == null
            reminderMessage = failure ?: "One optional reminder per day is enabled."
            if (failure != null) {
                WellbeingReminderReceiver.cancel(context)
                preferences.edit().putBoolean("reminder_enabled", false).apply()
            }
        } else {
            WellbeingReminderReceiver.cancel(context)
            reminderEnabled = false
            preferences.edit().putBoolean("reminder_enabled", false).apply()
            reminderMessage = "Notification permission was denied. Wellbeing reminders remain disabled."
        }
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Camera assessment", style = MaterialTheme.typography.titleLarge)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(if (cameraEnabled) "Enabled" else "Disabled")
                    Switch(checked = cameraEnabled, onCheckedChange = onCameraEnabled)
                }
                Text("Disable to remove the optional camera workflow from the Wellbeing Hub.")
            }
        }
        WhiteCard {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Store camera feature history", style = MaterialTheme.typography.titleMedium)
                    Text("When off, structured camera features exist only in the current result screen.")
                }
                Switch(checked = storeCameraHistory, onCheckedChange = onStoreCameraHistory)
            }
        }
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Daily check-in reminder", style = MaterialTheme.typography.titleLarge)
                Text("Optional, no more than once a day. Android notification permission is respected.")
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(if (reminderEnabled) "Enabled" else "Disabled")
                    Switch(
                        checked = reminderEnabled,
                        onCheckedChange = { enable ->
                            if (!enable) {
                                WellbeingReminderReceiver.cancel(context)
                                reminderEnabled = false
                                preferences.edit().putBoolean("reminder_enabled", false).apply()
                                reminderMessage = "Reminder disabled."
                            } else if (Build.VERSION.SDK_INT >= 33 &&
                                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
                                PackageManager.PERMISSION_GRANTED
                            ) {
                                notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                            } else {
                                val failure = scheduleWellbeingReminder(context, preferences, reminderTime)
                                reminderEnabled = failure == null
                                reminderMessage = failure ?: "One optional reminder per day is enabled."
                                if (failure != null) {
                                    WellbeingReminderReceiver.cancel(context)
                                    preferences.edit().putBoolean("reminder_enabled", false).apply()
                                }
                            }
                        },
                    )
                }
                OutlinedTextField(
                    value = reminderTime,
                    onValueChange = { reminderTime = it.take(5) },
                    label = { Text("Reminder time (24-hour HH:mm)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedButton(
                    onClick = {
                        if (!reminderEnabled) {
                            reminderMessage = "Enable reminders to save a daily reminder time."
                        } else if (Build.VERSION.SDK_INT >= 33 &&
                            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
                            PackageManager.PERMISSION_GRANTED
                        ) {
                            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                        } else {
                            reminderMessage = scheduleWellbeingReminder(context, preferences, reminderTime)
                                ?: "Reminder time saved."
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Save Reminder Time") }
                reminderMessage?.let { Text(it) }
            }
        }
        WhiteCard {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Camera privacy", style = MaterialTheme.typography.titleLarge)
                Text("Raw video retention: OFF and not implemented")
                Text("Raw video sent to Gemini: No")
                Text("Identity recognition: Not implemented")
                Text("Camera permission: Requested only when you start the assessment")
                Text("Camera: Active only during the foreground assessment")
                Text("Frames: Released after processing; only structured observations may be saved")
                Text("Camera observation data is kept separate from self-reported, sleep, and calculated recovery sources.")
            }
        }
    }
}

private data class HistoryRow(val timestampMs: Long, val type: String, val summary: String, val source: String)

@Composable
private fun WhiteCard(content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = androidx.compose.ui.graphics.Color.White),
    ) {
        Column(Modifier.padding(18.dp), content = content)
    }
}

@Composable
private fun MetricRow(label: String, value: String?, source: String?) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(label)
            source?.let { Text(it.replace('_', ' '), style = MaterialTheme.typography.labelSmall) }
        }
        Text(value ?: "Not recorded", fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun MessageCard(text: String, error: Boolean) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (error) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer,
        ),
    ) {
        Text(text, Modifier.padding(12.dp))
    }
}

private fun scaleLabel(value: Int, direction: String): String = when {
    value == 1 -> "Very Low"
    value == 2 -> "Low"
    value == 3 -> "Moderate"
    value == 4 && direction == "positive" -> "Good"
    value == 5 && direction == "positive" -> "Excellent"
    value == 4 -> "High"
    else -> "Very High"
}

private fun durationLabel(minutes: Int): String = "${minutes / 60}h ${minutes % 60}m"

private fun movementLevel(value: Double): String = when {
    value < 0.025 -> "Low observed movement"
    value < 0.08 -> "Moderate observed movement"
    else -> "Variable observed movement"
}

private fun formatValue(value: Double): String =
    if (value % 1.0 == 0.0) value.toInt().toString() else "%.1f".format(Locale.US, value)

private fun isToday(timestampMs: Long): Boolean =
    java.time.Instant.ofEpochMilli(timestampMs).atZone(ZoneId.systemDefault()).toLocalDate() == LocalDate.now()

private fun readableFactors(json: String): String = try {
    val factors = com.google.gson.JsonParser.parseString(json).asJsonObject
    factors.entrySet().joinToString { (key, value) -> "${key.replace('_', ' ')} ${value.asJsonObject.get("value")}" }
        .ifBlank { "No measured factors" }
} catch (_: Exception) {
    "Supporting factors recorded"
}

private fun scheduleWellbeingReminder(
    context: Context,
    preferences: android.content.SharedPreferences,
    time: String,
): String? {
    val parsed = try {
        LocalTime.parse(time)
    } catch (_: java.time.format.DateTimeParseException) {
        return "Enter a valid 24-hour time such as 19:00."
    }
    try {
        WellbeingReminderReceiver.schedule(context, parsed)
    } catch (_: SecurityException) {
        return "Android did not allow the reminder to be scheduled."
    }
    preferences.edit().putBoolean("reminder_enabled", true).putString("reminder_time", time).apply()
    return null
}

private const val MAX_WELLBEING_NOTE_LENGTH = 500
private const val MAX_SESSION_OBSERVATIONS = 300

private tailrec fun Context.findActivity(): android.app.Activity? = when (this) {
    is android.app.Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

private data class TrendSeries(
    val name: String,
    val trendValues: List<Double>,
    val rawValues: List<Double>,
    val source: String,
)
