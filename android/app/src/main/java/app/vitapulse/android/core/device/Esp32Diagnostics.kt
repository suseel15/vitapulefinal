package app.vitapulse.android.core.device

class Esp32Diagnostics {
    private var successes = 0L
    private var failures = 0L
    private var invalid = 0L
    private var timeouts = 0L
    private var stale = 0L
    private var latencyTotal = 0L
    private var maxLatency = 0L
    private var firstSuccess: Long? = null
    private var lastSuccess: Long? = null
    private var lastError: String? = null

    @Synchronized
    fun recordSuccess(latencyMs: Long, receivedAtMs: Long = android.os.SystemClock.elapsedRealtime()) {
        successes += 1
        latencyTotal += latencyMs
        maxLatency = maxOf(maxLatency, latencyMs)
        if (firstSuccess == null) firstSuccess = receivedAtMs
        lastSuccess = receivedAtMs
        lastError = null
    }

    @Synchronized
    fun recordFailure(error: Throwable) {
        failures += 1
        if (error is java.net.SocketTimeoutException) timeouts += 1
        lastError = error.message ?: error.javaClass.simpleName
    }

    @Synchronized
    fun recordInvalid(reason: String) {
        invalid += 1
        lastError = reason
    }

    @Synchronized
    fun recordStale() {
        stale += 1
    }

    @Synchronized
    fun reset() {
        successes = 0
        failures = 0
        invalid = 0
        timeouts = 0
        stale = 0
        latencyTotal = 0
        maxLatency = 0
        firstSuccess = null
        lastSuccess = null
        lastError = null
    }

    @Synchronized
    fun snapshot(internetAvailable: Boolean = false): SensorDiagnostics {
        val elapsed = (lastSuccess ?: 0L) - (firstSuccess ?: 0L)
        val rate = if (successes > 1 && elapsed > 0) (successes - 1) * 1000.0 / elapsed else null
        return SensorDiagnostics(
            successfulRequests = successes,
            failedRequests = failures,
            invalidSamples = invalid,
            timeouts = timeouts,
            staleReadings = stale,
            averageLatencyMs = if (successes > 0) latencyTotal.toDouble() / successes else null,
            maxLatencyMs = maxLatency,
            measuredRateHz = rate,
            lastSuccessAtMs = lastSuccess,
            lastError = lastError,
            internetAvailable = internetAvailable,
        )
    }
}
