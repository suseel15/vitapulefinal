package app.vitapulse.android.feature.connect

import android.content.Intent
import android.content.ActivityNotFoundException
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.HealthAndSafety
import androidx.compose.material.icons.filled.MonitorHeart
import androidx.compose.material.icons.filled.Sensors
import androidx.compose.material.icons.filled.Watch
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.health.connect.client.PermissionController
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.room.Room
import app.vitapulse.android.VitaPulseApplication
import app.vitapulse.android.core.device.MovementConnectionState
import app.vitapulse.android.core.healthconnect.HealthConnectAvailability
import app.vitapulse.android.core.healthconnect.HealthConnectPermissionManager
import app.vitapulse.android.core.healthconnect.HealthConnectSyncRepository
import app.vitapulse.android.core.healthconnect.HealthConnectSyncWorker
import app.vitapulse.android.core.healthconnect.HealthDataEntity
import app.vitapulse.android.core.healthconnect.HealthDataType
import app.vitapulse.android.core.healthconnect.HealthSyncStatus
import app.vitapulse.android.core.healthconnect.HealthSyncRunEntity
import app.vitapulse.android.core.healthconnect.UnifiedHealthRecord
import app.vitapulse.android.core.healthconnect.deduplicationKey
import app.vitapulse.android.core.healthconnect.isValid
import com.google.gson.JsonParser
import kotlinx.coroutines.launch
import kotlinx.coroutines.CancellationException
import retrofit2.HttpException
import java.io.IOException
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@Composable
@OptIn(ExperimentalMaterial3Api::class)
fun ConnectFeatureScreen(
    movementState: MovementConnectionState,
    onOpenMovementDevice: () -> Unit,
    onTestMovementDevice: () -> Unit,
    initialRoute: String = "hub",
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val app = context.applicationContext as VitaPulseApplication
    var healthConnectClient by remember { mutableStateOf(app.healthConnectClient) }
    val permissionManager = remember(healthConnectClient) {
        healthConnectClient?.let(::HealthConnectPermissionManager)
    }
    var availability by remember { mutableStateOf(app.healthConnectManager.availability()) }
    val allTypes = remember { HealthDataType.entries.toSet() }
    var grantedPermissions by remember { mutableStateOf(emptySet<String>()) }
    var route by remember(initialRoute) { mutableStateOf(initialRoute) }
    var selectedPermissionTypes by remember { mutableStateOf<Set<HealthDataType>>(emptySet()) }
    var showDataDisclosure by remember { mutableStateOf(false) }
    var showDeleteConfirmation by remember { mutableStateOf(false) }
    var showRemoteDeleteConfirmation by remember { mutableStateOf(false) }
    var syncBusy by remember { mutableStateOf(false) }
    var syncMessage by remember { mutableStateOf<String?>(null) }
    var syncError by remember { mutableStateOf<String?>(null) }
    var deleteError by remember { mutableStateOf<String?>(null) }
    var healthDataSyncEnabled by remember { mutableStateOf(app.backendClient.isHealthDataSyncEnabled()) }
    var persistedPermissions by remember { mutableStateOf<Set<String>?>(null) }
    val scope = rememberCoroutineScope()
    val lifecycleOwner = LocalLifecycleOwner.current
    val dao = app.healthDataDatabase.healthDataDao()
    val records by dao.observeRecentRecords().collectAsState(initial = emptyList())
    val syncRuns by dao.observeSyncRuns().collectAsState(initial = emptyList())
    val pendingUploads by dao.observePendingBackendCount().collectAsState(initial = 0)
    var lastReportedMovementState by remember { mutableStateOf<MovementConnectionState?>(null) }

    suspend fun refreshPermissions(manager: HealthConnectPermissionManager? = permissionManager) {
        val current = manager?.grantedPermissions() ?: emptySet()
        grantedPermissions = current
        if (persistedPermissions != current) {
            persistedPermissions = current
            if (healthDataSyncEnabled && manager != null) {
                try {
                    val checkedAt = Instant.now().toString()
                    allTypes.forEach { type ->
                        val isGranted = manager.requiredPermissions(setOf(type)).all { it in current }
                        app.backendClient.saveHealthConnectPermission(
                            type.name,
                            if (isGranted) "GRANTED" else "DENIED",
                            checkedAt,
                        )
                    }
                } catch (_: IOException) {
                    syncError = "Permission status could not be synchronized. It remains available on this device."
                } catch (error: HttpException) {
                    syncError = "Permission status could not be synchronized (HTTP ${error.code()})."
                } catch (error: IllegalStateException) {
                    syncError = error.message ?: "Permission status could not be synchronized."
                }
            }
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = PermissionController.createRequestPermissionResultContract(),
    ) { permissions ->
        grantedPermissions = permissions
        scope.launch { refreshPermissions() }
    }

    DisposableEffect(lifecycleOwner, permissionManager) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                val client = app.refreshHealthConnectClient()
                healthConnectClient = client
                availability = app.healthConnectManager.availability()
                val refreshedManager = client?.let(::HealthConnectPermissionManager)
                scope.launch { refreshPermissions(refreshedManager) }
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    LaunchedEffect(movementState) {
        val previousState = lastReportedMovementState
        lastReportedMovementState = movementState
        val isConnected = movementState == MovementConnectionState.SENSOR_CONNECTED
        val wasConnected = previousState == MovementConnectionState.SENSOR_CONNECTED
        if (isConnected || wasConnected) {
            try {
                app.backendClient.saveConnectedDevice(
                    deviceType = "ESP32",
                    brand = "ESP32",
                    model = "MPU6050",
                    identifier = "ESP32-001",
                    connectionType = "HTTP",
                    status = if (isConnected) "CONNECTED" else "DISCONNECTED",
                )
            } catch (_: IOException) {
                syncError = "The ESP32 status is current on this device but could not be synchronized to your account."
            } catch (error: HttpException) {
                syncError = "The ESP32 status could not be synchronized (HTTP ${error.code()})."
            } catch (error: IllegalStateException) {
                if (previousState != null) {
                    syncError = error.message ?: "Sign in to synchronize device status."
                }
            }
        }
    }

    BackHandler(enabled = route != "hub") {
        route = when {
            route.startsWith("watch") -> "hub"
            route.startsWith("health") -> "hub"
            route.startsWith("sync") -> "hub"
            route == "permissions" || route == "diagnostics" || route == "settings" -> "hub"
            else -> "hub"
        }
    }

    fun startContextualPermissionRequest(types: Set<HealthDataType>) {
        selectedPermissionTypes = types
        showDataDisclosure = true
    }

    fun performSync() {
        val repository = app.healthSyncRepository
        if (repository == null) {
            syncError = when (availability) {
                HealthConnectAvailability.NEEDS_UPDATE -> "Health Connect needs an update on this device."
                HealthConnectAvailability.UNAVAILABLE -> "Health Connect is unavailable on this device."
                HealthConnectAvailability.AVAILABLE -> "Health Connect could not be initialized."
            }
            return
        }
        scope.launch {
            syncBusy = true
            syncError = null
            syncMessage = "Checking permissions and reading recent records…"
            try {
                val result = repository.sync(allTypes)
                if (app.backendClient.isHealthDataSyncEnabled()) {
                    HealthConnectSyncWorker.enqueueImmediate(context)
                }
                syncMessage = when (result.status) {
                    HealthSyncStatus.SYNCED -> "Sync complete: ${result.recordsImported} new records imported."
                    HealthSyncStatus.NO_DATA -> "No recent authorized Health Connect records were found."
                    HealthSyncStatus.PARTIAL -> "Sync partially complete: ${result.recordsImported} imported, ${result.recordsSkipped} duplicates skipped."
                    HealthSyncStatus.PERMISSION_REQUIRED -> "Grant the requested data permissions to sync those record types."
                    else -> "Sync status: ${result.status.name.lowercase().replace('_', ' ')}."
                }
                syncError = result.errors.entries.firstOrNull { it.value != "NO_DATA" }?.let {
                    "${it.key.label}: ${it.value.lowercase().replace('_', ' ')}"
                }
                refreshPermissions()
            } catch (error: SecurityException) {
                syncError = "Health Connect permission changed. Review permissions and try again."
                refreshPermissions()
            } catch (error: java.io.IOException) {
                syncError = "Health Connect could not be reached. Try again when it is available."
            } finally {
                syncBusy = false
            }
        }
    }

    Scaffold(
        modifier = modifier,
        topBar = {
            if (route != "hub") {
                TopAppBar(
                    title = { Text(routeTitle(route)) },
                    navigationIcon = {
                        TextButton(onClick = { route = "hub" }) {
                            Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                            Text("Back")
                        }
                    },
                )
            }
        },
    ) { insets ->
        when (route) {
            "hub" -> ConnectHub(
                modifier = Modifier.fillMaxSize().padding(insets),
                movementState = movementState,
                availability = availability,
                grantedPermissions = grantedPermissions,
                permissionManager = permissionManager,
                allTypes = allTypes,
                companionInstalled = isNoiseFitInstalled(context.packageManager),
                records = records,
                pendingUploads = pendingUploads,
                healthDataSyncEnabled = healthDataSyncEnabled,
                syncBusy = syncBusy,
                syncMessage = syncMessage,
                syncError = syncError,
                onOpenMovementDevice = onOpenMovementDevice,
                onOpenWatch = { route = "watch-setup" },
                onOpenHealthConnect = { route = "health-data" },
                onOpenSync = { route = "sync" },
                onOpenDiagnostics = { route = "diagnostics" },
                onSync = ::performSync,
            )
            "watch-setup" -> WatchSetupScreen(
                modifier = Modifier.fillMaxSize().padding(insets),
                companionInstalled = remember { isNoiseFitInstalled(context.packageManager) },
                onOpenCompanion = {
                    context.packageManager.getLaunchIntentForPackage(NOISEFIT_PACKAGE)?.let(context::startActivity)
                },
                onCheck = {
                    scope.launch {
                        refreshPermissions()
                        route = "watch-status"
                    }
                },
            )
            "watch-status" -> WatchStatusScreen(
                modifier = Modifier.fillMaxSize().padding(insets),
                companionInstalled = remember { isNoiseFitInstalled(context.packageManager) },
                grantedPermissions = grantedPermissions,
                permissionManager = permissionManager,
                records = records,
                onOpenCompanion = {
                    context.packageManager.getLaunchIntentForPackage(NOISEFIT_PACKAGE)?.let(context::startActivity)
                },
                onPermissions = { route = "health-permissions" },
            )
            "health-permissions" -> HealthPermissionsScreen(
                modifier = Modifier.fillMaxSize().padding(insets),
                availability = availability,
                grantedPermissions = grantedPermissions,
                permissionManager = permissionManager,
                onRequest = { type -> startContextualPermissionRequest(setOf(type)) },
                onRequestAll = { startContextualPermissionRequest(allTypes) },
                onManage = {
                    runCatching {
                        context.startActivity(Intent("androidx.health.ACTION_HEALTH_CONNECT_SETTINGS"))
                    }.onFailure { error ->
                        val providerPackage = if (android.os.Build.VERSION.SDK_INT >= 34) {
                            "com.google.android.healthconnect.controller"
                        } else {
                            "com.google.android.apps.healthdata"
                        }
                        try {
                            context.startActivity(
                                Intent(
                                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                    Uri.parse("package:$providerPackage"),
                                ),
                            )
                        } catch (settingsError: ActivityNotFoundException) {
                            syncError = "Health Connect settings could not be opened: ${settingsError.message ?: error.message}"
                        } catch (settingsError: SecurityException) {
                            syncError = "Health Connect settings are unavailable: ${settingsError.message}"
                        }
                    }
                },
            )
            "health-data" -> HealthDataScreen(Modifier.fillMaxSize().padding(insets), records)
            "sync" -> SyncDashboardScreen(
                modifier = Modifier.fillMaxSize().padding(insets),
                availability = availability,
                grantedPermissions = grantedPermissions,
                permissionManager = permissionManager,
                records = records,
                syncRuns = syncRuns,
                busy = syncBusy,
                message = syncMessage,
                error = syncError,
                onSync = ::performSync,
                onHistory = { route = "sync-history" },
                onManagePermissions = { route = "health-permissions" },
            )
            "sync-history" -> SyncHistoryScreen(Modifier.fillMaxSize().padding(insets), syncRuns)
            "diagnostics" -> DiagnosticsScreen(
                modifier = Modifier.fillMaxSize().padding(insets),
                movementState = movementState,
                availability = availability,
                companionInstalled = isNoiseFitInstalled(context.packageManager),
                records = records,
                onTestMovement = onTestMovementDevice,
                onTestHealthConnect = { scope.launch { refreshPermissions() } },
                onSync = ::performSync,
                onBackend = {
                    syncError = "Sign in to an athlete account and configure the VitaPulse API to run backend diagnostics."
                },
            )
            "permissions" -> ConnectPermissionsScreen(
                modifier = Modifier.fillMaxSize().padding(insets),
                availability = availability,
                grantedPermissions = grantedPermissions,
                permissionManager = permissionManager,
                onHealthPermissions = { route = "health-permissions" },
                onRequestAllHealthData = { startContextualPermissionRequest(allTypes) },
                onOpenAppSettings = {
                    context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}")))
                },
            )
            "settings" -> ConnectSettingsScreen(
                modifier = Modifier.fillMaxSize().padding(insets),
                healthDataSyncEnabled = healthDataSyncEnabled,
                onHealthDataSyncChanged = { enabled ->
                    healthDataSyncEnabled = enabled
                    app.backendClient.setHealthDataSyncEnabled(enabled)
                    if (enabled) {
                        persistedPermissions = null
                        HealthConnectSyncWorker.schedulePeriodic(context)
                        scope.launch {
                            refreshPermissions()
                            HealthConnectSyncWorker.enqueueImmediate(context)
                        }
                    } else {
                        HealthConnectSyncWorker.cancelBackground(context)
                    }
                },
                onManagePermissions = { route = "health-permissions" },
                onOpenNoiseFit = {
                    context.packageManager.getLaunchIntentForPackage(NOISEFIT_PACKAGE)?.let(context::startActivity)
                },
                onReset = { showDeleteConfirmation = true },
                onDeleteAccountData = {
                    showRemoteDeleteConfirmation = true
                    deleteError = null
                },
            )
            else -> ConnectHub(
                modifier = Modifier.fillMaxSize().padding(insets),
                movementState = movementState,
                availability = availability,
                grantedPermissions = grantedPermissions,
                permissionManager = permissionManager,
                allTypes = allTypes,
                companionInstalled = isNoiseFitInstalled(context.packageManager),
                records = records,
                pendingUploads = pendingUploads,
                healthDataSyncEnabled = healthDataSyncEnabled,
                syncBusy = syncBusy,
                syncMessage = syncMessage,
                syncError = syncError,
                onOpenMovementDevice = onOpenMovementDevice,
                onOpenWatch = { route = "watch-setup" },
                onOpenHealthConnect = { route = "health-data" },
                onOpenSync = { route = "sync" },
                onOpenDiagnostics = { route = "diagnostics" },
                onSync = ::performSync,
            )
        }
    }

    if (showDataDisclosure) {
        val types = selectedPermissionTypes
        val labels = types.sortedBy { it.ordinal }.joinToString { it.label }
        AlertDialog(
            onDismissRequest = { showDataDisclosure = false },
            title = { Text(if (types.size > 1) "Connect supported health data" else "Health Data Access") },
            text = {
                Text(
                    "VitaPulse will request read access to $labels. Data can support recovery, activity, and wellbeing features. " +
                        "The Health Connect system screen lets you approve or decline each permission, and you can revoke access at any time. " +
                        "VitaPulse does not request write access.",
                )
            },
            confirmButton = {
                TextButton(
                    enabled = types.isNotEmpty() && permissionManager != null,
                    onClick = {
                        if (types.isEmpty()) return@TextButton
                        val manager = permissionManager ?: return@TextButton
                        scope.launch {
                            try {
                                val missing = manager.missingPermissions(types)
                                showDataDisclosure = false
                                if (missing.isNotEmpty()) permissionLauncher.launch(missing)
                            } catch (error: CancellationException) {
                                throw error
                            } catch (error: Exception) {
                                showDataDisclosure = false
                                syncError = "Health Connect could not open the permission request: ${error.message ?: error.javaClass.simpleName}"
                            }
                        }
                    },
                ) { Text("Continue") }
            },
            dismissButton = {
                TextButton(onClick = { showDataDisclosure = false }) { Text("Cancel") }
            },
        )
    }

    if (showDeleteConfirmation) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirmation = false },
            title = { Text("Delete VitaPulse health-data copies?") },
            text = {
                Text(
                    "This deletes Health Connect data cached in VitaPulse on this device. It does not delete data in Health Connect or the VitaPulse account. Manage those separately.",
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        app.healthSyncRepository?.deleteAllHealthConnectData()
                        showDeleteConfirmation = false
                        route = "hub"
                    }
                }) { Text("Delete VitaPulse copies") }
            },
            dismissButton = { TextButton(onClick = { showDeleteConfirmation = false }) { Text("Cancel") } },
        )
    }

    if (showRemoteDeleteConfirmation) {
        AlertDialog(
            onDismissRequest = { showRemoteDeleteConfirmation = false },
            title = { Text("Delete account Health Connect data?") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "This removes Health Connect summaries, permissions metadata, and sync history from your VitaPulse account and this device.",
                    )
                    Text(
                        "It does not revoke Health Connect access. Manage or revoke that permission in Health Connect settings.",
                    )
                    deleteError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        scope.launch {
                            deleteError = null
                            try {
                                app.backendClient.deleteHealthConnectAccountData()
                                app.healthSyncRepository?.deleteAllHealthConnectData()
                                app.backendClient.setHealthDataSyncEnabled(false)
                                healthDataSyncEnabled = false
                                HealthConnectSyncWorker.cancelBackground(context)
                                showRemoteDeleteConfirmation = false
                                route = "hub"
                            } catch (_: IOException) {
                                deleteError = "The account data could not be deleted because the service is unavailable. Try again."
                            } catch (error: HttpException) {
                                deleteError = "The account data could not be deleted (HTTP ${error.code()})."
                            } catch (error: IllegalStateException) {
                                deleteError = error.message ?: "Sign in before deleting account health data."
                            }
                        }
                    },
                ) { Text("Delete account data") }
            },
            dismissButton = {
                TextButton(onClick = { showRemoteDeleteConfirmation = false }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun ConnectHub(
    modifier: Modifier,
    movementState: MovementConnectionState,
    availability: HealthConnectAvailability,
    grantedPermissions: Set<String>,
    permissionManager: HealthConnectPermissionManager?,
    allTypes: Set<HealthDataType>,
    companionInstalled: Boolean,
    records: List<HealthDataEntity>,
    pendingUploads: Int,
    healthDataSyncEnabled: Boolean,
    syncBusy: Boolean,
    syncMessage: String?,
    syncError: String?,
    onOpenMovementDevice: () -> Unit,
    onOpenWatch: () -> Unit,
    onOpenHealthConnect: () -> Unit,
    onOpenSync: () -> Unit,
    onOpenDiagnostics: () -> Unit,
    onSync: () -> Unit,
) {
    val approvedTypes = permissionManager?.let { manager ->
        allTypes.filter { type -> permissionGranted(manager, grantedPermissions, type) }.toSet()
    } ?: emptySet()
    val latestSync = records.maxOfOrNull { it.syncedAtMs }?.let(::formatEpoch) ?: "No data synchronized"
    LazyColumn(
        modifier = modifier.padding(horizontal = 18.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Column(Modifier.padding(top = 16.dp, bottom = 4.dp)) {
                Text("Connect", style = MaterialTheme.typography.headlineMedium)
                Text("Keep your devices and health data connected to VitaPulse.")
            }
        }
        item {
            ConnectCard(
                icon = { Icon(Icons.Default.Sensors, contentDescription = null) },
                title = "ESP32 + MPU6050",
                status = movementState.name.replace('_', ' '),
                details = listOf("Device: ESP32-001", "Transport: HTTP", "Address: 192.168.4.1", "Polling: approximately 10 Hz"),
                action = "Open movement device",
                onClick = onOpenMovementDevice,
            )
        }
        item {
            ConnectCard(
                icon = { Icon(Icons.Default.Watch, contentDescription = null) },
                title = "NoiseFit Mettle",
                status = if (companionInstalled) "Companion app detected" else "Not linked",
                details = listOf(
                    if (companionInstalled) "NoiseFit app is installed; watch pairing is managed there." else "Install and pair through the official NoiseFit app.",
                    "Health Connect permissions: ${approvedTypes.size} of ${allTypes.size} approved",
                    "Watch metrics appear only when Health Connect returns actual records.",
                ),
                action = "Set up watch",
                onClick = onOpenWatch,
            )
        }
        item {
            val availabilityText = when (availability) {
                HealthConnectAvailability.AVAILABLE -> when {
                    approvedTypes.isEmpty() -> "Available · permissions not granted"
                    approvedTypes.size == allTypes.size -> "Authorized for selected data"
                    else -> "Partially authorized · ${approvedTypes.size} of ${allTypes.size} types"
                }
                HealthConnectAvailability.NEEDS_UPDATE -> "Health Connect needs an update"
                HealthConnectAvailability.UNAVAILABLE -> "Unavailable on this device"
            }
            ConnectCard(
                icon = { Icon(Icons.Default.HealthAndSafety, contentDescription = null) },
                title = "Health Connect",
                status = availabilityText,
                details = listOf(
                    "Allowed data: ${approvedTypes.map { it.label }.ifEmpty { listOf("None") }.joinToString(" · ")}",
                    "Local records: ${records.size}",
                    "Last sync: $latestSync",
                    "Account upload queue: $pendingUploads ${if (healthDataSyncEnabled) "pending or offline" else "not enabled"}",
                ),
                action = "Manage health data",
                onClick = onOpenHealthConnect,
            )
        }
        item {
            Button(onClick = onSync, enabled = !syncBusy && availability == HealthConnectAvailability.AVAILABLE) {
                if (syncBusy) CircularProgressIndicator()
                else Text("Sync All")
            }
            Spacer(Modifier.height(4.dp))
            OutlinedButton(onClick = onOpenSync) { Text("Sync dashboard and history") }
            OutlinedButton(onClick = onOpenDiagnostics) { Text("Diagnostics") }
        }
        if (syncMessage != null || syncError != null) {
            item {
                syncMessage?.let { StatusCard(it, isError = false) }
                syncError?.let { StatusCard(it, isError = true) }
            }
        }
        item {
            OutlinedButton(onClick = onOpenWatch) { Text("Watch setup") }
        }
    }
}

@Composable
private fun WatchSetupScreen(
    modifier: Modifier,
    companionInstalled: Boolean,
    onOpenCompanion: () -> Unit,
    onCheck: () -> Unit,
) {
    LazyColumn(modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("NoiseFit Mettle setup", style = MaterialTheme.typography.headlineSmall) }
        item { Text("VitaPulse does not pair with or control the watch directly. Use the official NoiseFit app, then share supported records through Health Connect where available.") }
        items(
            listOf(
                "Install or open NoiseFit.",
                "Pair NoiseFit Mettle inside NoiseFit.",
                "Complete the official watch setup and grant the permissions you choose.",
                "Enable and synchronize supported health data in the NoiseFit ecosystem.",
                "Connect only the selected Health Connect data types in VitaPulse.",
                "Return to VitaPulse and check for actual imported records.",
            ),
        ) { step ->
            Text("•  $step")
        }
        item {
            if (companionInstalled) Button(onClick = onOpenCompanion) { Text("Open NoiseFit") }
            else StatusCard("NoiseFit app not detected. Install the official companion app, pair the watch there, and return here.", false)
        }
        item { OutlinedButton(onClick = onCheck) { Text("Check Health Connect") } }
        item {
            Text("NoiseFit may need to remain active or locked in the background for its own Bluetooth synchronization. VitaPulse cannot repair its proprietary watch connection.")
        }
    }
}

@Composable
private fun WatchStatusScreen(
    modifier: Modifier,
    companionInstalled: Boolean,
    grantedPermissions: Set<String>,
    permissionManager: HealthConnectPermissionManager?,
    records: List<HealthDataEntity>,
    onOpenCompanion: () -> Unit,
    onPermissions: () -> Unit,
) {
    LazyColumn(modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("NoiseFit Mettle", style = MaterialTheme.typography.headlineSmall) }
        item { Text("Connection: ${if (companionInstalled) "companion app detected; watch connection not independently verified" else "not linked"}") }
        item { Text("VitaPulse does not receive watch pairing credentials or battery status.") }
        items(HealthDataType.entries.toList()) { type ->
            val allowed = permissionManager?.let { permissionGranted(it, grantedPermissions, type) } == true
            val latest = records.filter { it.dataType == type.name }.maxByOrNull { it.recordEndMs }
            Text(
                "${type.label}: ${when { !allowed -> "permission not granted"; latest == null -> "no recent Health Connect record"; else -> "available · ${formatEpoch(latest.recordEndMs)} · Health Connect" }}",
            )
        }
        item { if (companionInstalled) Button(onClick = onOpenCompanion) { Text("Open NoiseFit") } }
        item { OutlinedButton(onClick = onPermissions) { Text("Manage Health Connect permissions") } }
    }
}

@Composable
private fun HealthPermissionsScreen(
    modifier: Modifier,
    availability: HealthConnectAvailability,
    grantedPermissions: Set<String>,
    permissionManager: HealthConnectPermissionManager?,
    onRequest: (HealthDataType) -> Unit,
    onRequestAll: () -> Unit,
    onManage: () -> Unit,
) {
    LazyColumn(modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Health Data Permissions", style = MaterialTheme.typography.headlineSmall) }
        item {
            Text(
                "Sleep supports recovery and wellbeing. Heart rate supports recovery context. Steps and exercise support activity context. Oxygen saturation is shown only when a connected source provides a real record.",
            )
        }
        item { Text("Status: ${availability.name.replace('_', ' ')}") }
        item {
            Button(
                onClick = onRequestAll,
                enabled = availability == HealthConnectAvailability.AVAILABLE && permissionManager != null,
            ) {
                Text("Connect all supported data")
            }
        }
        items(HealthDataType.entries.toList()) { type ->
            val granted = permissionManager?.let { permissionGranted(it, grantedPermissions, type) } == true
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("${type.label} · ${if (granted) "Allowed" else "Not allowed"}")
                if (!granted && availability == HealthConnectAvailability.AVAILABLE) {
                    TextButton(onClick = { onRequest(type) }) { Text("Connect") }
                }
            }
        }
        item { Button(onClick = onManage) { Text("Open Health Connect settings") } }
    }
}

@Composable
private fun HealthDataScreen(modifier: Modifier, records: List<HealthDataEntity>) {
    LazyColumn(modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Health Connect data", style = MaterialTheme.typography.headlineSmall) }
        item { Text("Record time and synchronization time are shown separately. Only records actually read from Health Connect appear here.") }
        if (records.isEmpty()) {
            item { StatusCard("No Health Connect records have been imported on this device.", false) }
        }
        items(records, key = { it.deduplicationKey }) { record ->
            HealthRecordCard(record)
        }
    }
}

@Composable
private fun SyncDashboardScreen(
    modifier: Modifier,
    availability: HealthConnectAvailability,
    grantedPermissions: Set<String>,
    permissionManager: HealthConnectPermissionManager?,
    records: List<HealthDataEntity>,
    syncRuns: List<HealthSyncRunEntity>,
    busy: Boolean,
    message: String?,
    error: String?,
    onSync: () -> Unit,
    onHistory: () -> Unit,
    onManagePermissions: () -> Unit,
) {
    LazyColumn(modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Health Data Sync", style = MaterialTheme.typography.headlineSmall) }
        item { Text("Last sync: ${syncRuns.firstOrNull()?.completedAtMs?.let(::formatEpoch) ?: "Not yet synchronized"}") }
        item {
            Text(
                "Initial import: sleep, steps, and exercise up to 30 days; heart rate and oxygen saturation up to 7 days. Each subsequent sync uses a bounded incremental window.",
            )
        }
        item { Text("Health Connect: ${availability.name.replace('_', ' ')}") }
        items(HealthDataType.entries.toList()) { type ->
            val granted = permissionManager?.let { permissionGranted(it, grantedPermissions, type) } == true
            val count = records.count { it.dataType == type.name }
            Text("${type.label}: ${if (!granted) "Permission required" else if (count == 0) "No recent data" else "$count cached records"}")
        }
        item {
            Button(onClick = onSync, enabled = !busy && availability == HealthConnectAvailability.AVAILABLE) {
                if (busy) CircularProgressIndicator() else Text("Sync All")
            }
            OutlinedButton(onClick = onManagePermissions) { Text("Manage permissions") }
            OutlinedButton(onClick = onHistory) { Text("Sync history") }
        }
        item { message?.let { StatusCard(it, false) } }
        item { error?.let { StatusCard(it, true) } }
    }
}

@Composable
private fun SyncHistoryScreen(modifier: Modifier, history: List<HealthSyncRunEntity>) {
    LazyColumn(modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Sync History", style = MaterialTheme.typography.headlineSmall) }
        if (history.isEmpty()) item { StatusCard("No synchronization has been recorded.", false) }
        items(history, key = { it.id }) { run ->
            Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Health Connect · ${run.status}")
                    Text("Started ${formatEpoch(run.startedAtMs)}")
                    run.completedAtMs?.let { Text("Completed ${formatEpoch(it)}") }
                    Text("${run.recordsImported} imported · ${run.recordsSkipped} duplicates skipped · ${run.recordsFailed} errors")
                    run.errorCode?.let { Text("Status: $it") }
                }
            }
        }
    }
}

@Composable
private fun DiagnosticsScreen(
    modifier: Modifier,
    movementState: MovementConnectionState,
    availability: HealthConnectAvailability,
    companionInstalled: Boolean,
    records: List<HealthDataEntity>,
    onTestMovement: () -> Unit,
    onTestHealthConnect: () -> Unit,
    onSync: () -> Unit,
    onBackend: () -> Unit,
) {
    LazyColumn(modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Connect Diagnostics", style = MaterialTheme.typography.headlineSmall) }
        item { Text("Movement device: ${movementState.name}") }
        item { Text("NoiseFit: ${if (companionInstalled) "companion installed; watch status not verified" else "not detected"}") }
        item { Text("Health Connect: ${availability.name}") }
        item { Text("Local Health Connect records: ${records.size}") }
        item { Button(onClick = onTestMovement) { Text("Test ESP32") } }
        item { Button(onClick = onTestHealthConnect) { Text("Test Health Connect permissions") } }
        item { Button(onClick = onSync) { Text("Sync Now") } }
        item { Button(onClick = onBackend) { Text("Test Backend") } }
    }
}

@Composable
private fun ConnectPermissionsScreen(
    modifier: Modifier,
    availability: HealthConnectAvailability,
    grantedPermissions: Set<String>,
    permissionManager: HealthConnectPermissionManager?,
    onHealthPermissions: () -> Unit,
    onRequestAllHealthData: () -> Unit,
    onOpenAppSettings: () -> Unit,
) {
    LazyColumn(modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Connect Permissions", style = MaterialTheme.typography.headlineSmall) }
        item { Text("Health Connect: ${availability.name}") }
        item { Text("Granted Health Connect scopes: ${grantedPermissions.size}") }
        item { Text("Local-network movement access is used only for the ESP32 connection.") }
        item { Text("Camera access is handled by its wellbeing feature when requested.") }
        item { Text("Notification permission is requested only by notification features.") }
        item {
            Button(
                onClick = onRequestAllHealthData,
                enabled = availability == HealthConnectAvailability.AVAILABLE && permissionManager != null,
            ) {
                Text("Request all supported health data")
            }
        }
        item { OutlinedButton(onClick = onHealthPermissions) { Text("Review health data permissions") } }
        item { OutlinedButton(onClick = onOpenAppSettings) { Text("Open Android app settings") } }
    }
}

@Composable
private fun ConnectSettingsScreen(
    modifier: Modifier,
    healthDataSyncEnabled: Boolean,
    onHealthDataSyncChanged: (Boolean) -> Unit,
    onManagePermissions: () -> Unit,
    onOpenNoiseFit: () -> Unit,
    onReset: () -> Unit,
    onDeleteAccountData: () -> Unit,
) {
    LazyColumn(modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Connect Settings", style = MaterialTheme.typography.headlineSmall) }
        item { Text("ESP32 default address: 192.168.4.1") }
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Column(Modifier.weight(1f)) {
                    Text("Background Health Connect sync", style = MaterialTheme.typography.titleMedium)
                    Text("Uploads summaries only to your signed-in VitaPulse account every six hours. Raw heart-rate samples stay on this device.")
                }
                Switch(checked = healthDataSyncEnabled, onCheckedChange = onHealthDataSyncChanged)
            }
        }
        item { OutlinedButton(onClick = onManagePermissions) { Text("Manage Health Connect") } }
        item { OutlinedButton(onClick = onOpenNoiseFit) { Text("Open NoiseFit if installed") } }
        item { OutlinedButton(onClick = onReset) { Text("Delete local Health Connect cache") } }
        item { Text("This deletion affects the local VitaPulse cache only; it does not delete Health Connect or account data.") }
        item { Button(onClick = onDeleteAccountData) { Text("Delete account Health Connect data") } }
    }
}

@Composable
private fun HealthRecordCard(record: HealthDataEntity) {
    val payload = runCatching { JsonParser.parseString(record.payloadJson).asJsonObject }.getOrNull()
    val summary = when (record.dataType) {
        HealthDataType.SLEEP.name -> {
            val minutes = payload?.get("durationMinutes")?.asLong
            minutes?.let { "${it / 60}h ${it % 60}m" } ?: "Sleep session"
        }
        HealthDataType.HEART_RATE.name -> {
            val samples = payload?.getAsJsonArray("samples")
            val values = samples?.mapNotNull { it.asJsonObject.get("beatsPerMinute")?.asLong } ?: emptyList()
            if (values.isEmpty()) "No heart-rate samples" else {
                val average = values.average().toInt()
                "$average bpm average · ${values.size} samples (general)"
            }
        }
        HealthDataType.STEPS.name -> payload?.get("count")?.asLong?.let { "$it steps" } ?: "Steps record"
        HealthDataType.EXERCISE.name -> payload?.get("title")?.asString?.takeIf { it.isNotBlank() } ?: "Exercise session"
        HealthDataType.OXYGEN_SATURATION.name -> payload?.get("percentage")?.asDouble?.let {
            "${"%.1f".format(it * 100)}% oxygen saturation"
        } ?: "Oxygen saturation record"
        else -> "Health Connect record"
    }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("${record.dataType.replace('_', ' ')} · $summary", style = MaterialTheme.typography.titleMedium)
            Text("Record time: ${formatEpoch(record.recordStartMs)}")
            Text("Synced: ${formatEpoch(record.syncedAtMs)}")
            Text("Source: Health Connect · ${record.sourceApplication}")
        }
    }
}

@Composable
private fun ConnectCard(
    icon: @Composable () -> Unit,
    title: String,
    status: String,
    details: List<String>,
    action: String,
    onClick: () -> Unit,
) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                icon()
                Text(title, style = MaterialTheme.typography.titleLarge)
            }
            Text("Status · $status")
            details.forEach { Text(it, style = MaterialTheme.typography.bodyMedium) }
            OutlinedButton(onClick = onClick) { Text(action) }
        }
    }
}

@Composable
private fun StatusCard(message: String, isError: Boolean) {
    Card(colors = CardDefaults.cardColors(containerColor = if (isError) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer)) {
        Row(Modifier.fillMaxWidth().padding(14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(
                if (isError) Icons.Default.ErrorOutline else Icons.Default.CheckCircle,
                contentDescription = if (isError) "Error" else "Status",
            )
            Text(message)
        }
    }
}

private fun permissionGranted(
    manager: HealthConnectPermissionManager,
    granted: Set<String>,
    type: HealthDataType,
): Boolean = runCatching { manager.requiredPermissions(setOf(type)).all { it in granted } }.getOrDefault(false)

private fun isNoiseFitInstalled(packageManager: android.content.pm.PackageManager): Boolean =
    runCatching { packageManager.getApplicationInfo(NOISEFIT_PACKAGE, 0) }.isSuccess

private fun routeTitle(route: String): String = when (route) {
    "watch-setup", "watch-status" -> "NoiseFit Mettle"
    "health-permissions" -> "Health Data Permissions"
    "health-data" -> "Health Connect Data"
    "sync" -> "Sync Dashboard"
    "sync-history" -> "Sync History"
    "diagnostics" -> "Diagnostics"
    "permissions" -> "Permissions"
    "settings" -> "Connect Settings"
    else -> "Connect"
}

private fun formatEpoch(epochMs: Long): String = DateTimeFormatter.ofPattern("d MMM yyyy · h:mm a")
    .withZone(ZoneId.systemDefault())
    .format(Instant.ofEpochMilli(epochMs))

private const val NOISEFIT_PACKAGE = "com.noisefit"
