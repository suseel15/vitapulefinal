package app.vitapulse.android

import android.app.Application
import androidx.room.Room
import app.vitapulse.android.core.device.BackendClient
import app.vitapulse.android.core.device.Esp32NetworkManager
import app.vitapulse.android.core.device.Esp32Repository
import app.vitapulse.android.core.device.HttpPollingMovementDataSource
import app.vitapulse.android.core.device.MovementDatabase
import app.vitapulse.android.core.device.MovementProcessor
import app.vitapulse.android.core.device.MovementDatabase.Companion.MIGRATION_1_2
import app.vitapulse.android.core.healthconnect.HealthConnectManager
import app.vitapulse.android.core.healthconnect.HealthConnectPermissionManager
import app.vitapulse.android.core.healthconnect.HealthConnectReader
import app.vitapulse.android.core.healthconnect.HealthConnectSyncRepository
import app.vitapulse.android.core.healthconnect.HealthConnectSyncWorker
import app.vitapulse.android.core.healthconnect.HealthDataDatabase
import app.vitapulse.android.core.healthconnect.HealthDataProvider
import app.vitapulse.android.core.healthconnect.HealthDataType
import app.vitapulse.android.feature.wellbeing.data.WellbeingDatabase
import app.vitapulse.android.movement.inference.ModelManager
import androidx.health.connect.client.HealthConnectClient

class VitaPulseApplication : Application() {
    lateinit var networkManager: Esp32NetworkManager
        private set
    lateinit var movementDataSource: HttpPollingMovementDataSource
        private set
    lateinit var movementDatabase: MovementDatabase
        private set
    lateinit var wellbeingDatabase: WellbeingDatabase
        private set
    lateinit var healthDataDatabase: HealthDataDatabase
        private set
    lateinit var healthConnectManager: HealthConnectManager
        private set
    var healthConnectClient: HealthConnectClient? = null
        private set
    var healthSyncRepository: HealthConnectSyncRepository? = null
        private set
    lateinit var backendClient: BackendClient
        private set
    lateinit var modelManager: ModelManager
        private set
    val movementProcessor by lazy { MovementProcessor() }

    override fun onCreate() {
        super.onCreate()
        networkManager = Esp32NetworkManager(this)
        movementDataSource = HttpPollingMovementDataSource(
            Esp32Repository(BuildConfig.ESP32_BASE_URL),
            BuildConfig.ESP32_POLL_INTERVAL_MS,
            BuildConfig.ESP32_STALE_TIMEOUT_MS,
        )
        movementDatabase = Room.databaseBuilder(
            this,
            MovementDatabase::class.java,
            "vitapulse-movement.db",
        ).addMigrations(MIGRATION_1_2).build()
        wellbeingDatabase = Room.databaseBuilder(
            this,
            WellbeingDatabase::class.java,
            "vitapulse-wellbeing.db",
        ).build()
        healthDataDatabase = Room.databaseBuilder(
            this,
            HealthDataDatabase::class.java,
            "vitapulse-health-data.db",
        ).build()
        healthConnectManager = HealthConnectManager(this)
        healthConnectClient = healthConnectManager.clientOrNull()
        healthConnectClient?.let { client ->
            healthSyncRepository = HealthConnectSyncRepository(
                healthDataDatabase,
                HealthConnectPermissionManager(client),
                HealthDataProvider { type, start, end -> HealthConnectReader(client).read(type, start, end) },
            )
        }
        backendClient = BackendClient(this)
        if (backendClient.isHealthDataSyncEnabled()) {
            HealthConnectSyncWorker.schedulePeriodic(this)
        }
        modelManager = ModelManager(this)
    }
}
