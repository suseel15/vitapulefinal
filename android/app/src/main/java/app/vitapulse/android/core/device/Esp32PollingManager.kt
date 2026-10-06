package app.vitapulse.android.core.device

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch

class Esp32PollingManager(
    private val source: MovementDataSource,
) {
    private var pollingJob: Job? = null

    fun start(scope: CoroutineScope, onSample: suspend (MovementSample) -> Unit, onError: (Throwable) -> Unit) {
        check(pollingJob?.isActive != true) { "Sensor polling is already active." }
        pollingJob = scope.launch {
            try {
                source.readings().collect(onSample)
            } catch (error: kotlinx.coroutines.CancellationException) {
                throw error
            } catch (error: Exception) {
                onError(error)
            }
        }
    }

    suspend fun stop() {
        pollingJob?.cancel()
        pollingJob?.join()
        pollingJob = null
    }
}
