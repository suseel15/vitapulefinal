package app.vitapulse.android.core.healthconnect

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.OxygenSaturationRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord

class HealthConnectManager(private val context: Context) {
    fun availability(): HealthConnectAvailability =
        when (HealthConnectClient.getSdkStatus(context)) {
            HealthConnectClient.SDK_AVAILABLE -> HealthConnectAvailability.AVAILABLE
            HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED -> HealthConnectAvailability.NEEDS_UPDATE
            else -> HealthConnectAvailability.UNAVAILABLE
        }

    fun clientOrNull(): HealthConnectClient? =
        if (availability() == HealthConnectAvailability.AVAILABLE) HealthConnectClient.getOrCreate(context) else null
}

class HealthConnectPermissionManager(private val client: HealthConnectClient) {
    fun requiredPermissions(types: Set<HealthDataType>): Set<String> = buildSet {
        if (HealthDataType.SLEEP in types) add(HealthPermission.getReadPermission(SleepSessionRecord::class))
        if (HealthDataType.HEART_RATE in types) add(HealthPermission.getReadPermission(HeartRateRecord::class))
        if (HealthDataType.STEPS in types) add(HealthPermission.getReadPermission(StepsRecord::class))
        if (HealthDataType.EXERCISE in types) add(HealthPermission.getReadPermission(ExerciseSessionRecord::class))
        if (HealthDataType.OXYGEN_SATURATION in types) {
            add(HealthPermission.getReadPermission(OxygenSaturationRecord::class))
        }
    }

    suspend fun grantedPermissions(): Set<String> = client.permissionController.getGrantedPermissions()

    suspend fun missingPermissions(types: Set<HealthDataType>): Set<String> =
        requiredPermissions(types) - grantedPermissions()

    suspend fun hasPermission(type: HealthDataType): Boolean =
        requiredPermissions(setOf(type)).all { it in grantedPermissions() }
}
