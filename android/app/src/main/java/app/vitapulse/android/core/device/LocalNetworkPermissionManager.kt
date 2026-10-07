package app.vitapulse.android.core.device

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat

class LocalNetworkPermissionManager(private val context: Context) {
    private val localNetworkPermission = "android.permission.ACCESS_LOCAL_NETWORK"

    fun state(): LocalNetworkPermissionState {
        val requestedPermission = permissionToRequest()
            ?: return LocalNetworkPermissionState.NOT_APPLICABLE
        return if (ContextCompat.checkSelfPermission(context, requestedPermission) == PackageManager.PERMISSION_GRANTED) {
            LocalNetworkPermissionState.GRANTED
        } else {
            LocalNetworkPermissionState.DENIED
        }
    }

    fun permissionToRequest(): String? {
        if (Build.VERSION.SDK_INT in Build.VERSION_CODES.Q..Build.VERSION_CODES.S_V2) {
            return Manifest.permission.ACCESS_FINE_LOCATION.takeIf {
                ContextCompat.checkSelfPermission(context, it) != PackageManager.PERMISSION_GRANTED
            }
        }
        if (Build.VERSION.SDK_INT >= 37) {
            return localNetworkPermission.takeIf {
                ContextCompat.checkSelfPermission(context, it) != PackageManager.PERMISSION_GRANTED
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.NEARBY_WIFI_DEVICES) != PackageManager.PERMISSION_GRANTED
        ) {
            return Manifest.permission.NEARBY_WIFI_DEVICES
        }
        return null
    }

    fun hasWifiConnectionPermission(): Boolean = permissionToRequest() == null
}
