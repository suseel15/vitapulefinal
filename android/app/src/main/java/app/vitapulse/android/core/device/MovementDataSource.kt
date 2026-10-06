package app.vitapulse.android.core.device

import android.net.Network
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow

interface MovementDataSource {
    suspend fun connect(network: Network)
    suspend fun disconnect()
    fun readings(): Flow<MovementSample>
    val connectionState: StateFlow<MovementConnectionState>
}

class SensorStreamException(
    val reason: String,
    val state: MovementConnectionState,
) : Exception(reason)
