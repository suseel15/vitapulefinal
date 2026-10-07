package app.vitapulse.android.core.device

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiNetworkSpecifier
import android.os.Build
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class Esp32NetworkManager(context: Context) {
    private val connectivityManager =
        context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    private var callback: ConnectivityManager.NetworkCallback? = null

    private val _connectionState = MutableStateFlow(MovementConnectionState.DISCONNECTED)
    val connectionState: StateFlow<MovementConnectionState> = _connectionState.asStateFlow()

    private val _network = MutableStateFlow<Network?>(null)
    val network: StateFlow<Network?> = _network.asStateFlow()

    private val _internetAvailable = MutableStateFlow(false)
    val internetAvailable: StateFlow<Boolean> = _internetAvailable.asStateFlow()

    init {
        connectivityManager.registerDefaultNetworkCallback(
            object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) = refreshInternetAvailability()
                override fun onLost(network: Network) = refreshInternetAvailability()
                override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) =
                    refreshInternetAvailability()
            },
        )
        refreshInternetAvailability()
    }

    fun requestEsp32Network(ssid: String = DEFAULT_SSID, passphrase: String) {
        releaseRequest()
        _connectionState.value = MovementConnectionState.REQUESTING_WIFI
        val specifierBuilder = WifiNetworkSpecifier.Builder().setSsid(ssid)
        if (passphrase.isNotBlank()) specifierBuilder.setWpa2Passphrase(passphrase)
        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .setNetworkSpecifier(specifierBuilder.build())
            .build()
        val networkCallback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                _network.value = network
                _connectionState.value = MovementConnectionState.CONNECTING
                refreshInternetAvailability()
            }

            override fun onLost(network: Network) {
                if (_network.value == network) {
                    _network.value = null
                    refreshInternetAvailability()
                    _connectionState.value = MovementConnectionState.WIFI_CONNECTION_FAILED
                }
            }

            override fun onUnavailable() {
                _network.value = null
                _connectionState.value = MovementConnectionState.WIFI_CONNECTION_FAILED
            }

            override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) {
                refreshInternetAvailability()
            }
        }
        callback = networkCallback
        try {
            connectivityManager.requestNetwork(request, networkCallback)
        } catch (error: SecurityException) {
            _connectionState.value = MovementConnectionState.NETWORK_PERMISSION_REQUIRED
            callback = null
            throw error
        }
    }

    private fun refreshInternetAvailability() {
        val activeNetwork = connectivityManager.activeNetwork
        val capabilities = activeNetwork?.let(connectivityManager::getNetworkCapabilities)
        _internetAvailable.value = capabilities?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true
    }

    fun markState(state: MovementConnectionState) {
        _connectionState.value = state
    }

    fun releaseRequest(manual: Boolean = false) {
        callback?.let {
            try {
                connectivityManager.unregisterNetworkCallback(it)
            } catch (_: IllegalArgumentException) {
                // A callback may already have been removed by the platform.
            }
        }
        callback = null
        _network.value = null
        refreshInternetAvailability()
        if (manual) _connectionState.value = MovementConnectionState.DISCONNECTED
    }

    companion object {
        const val DEFAULT_SSID = "VitaPulse-ESP32"
    }
}
