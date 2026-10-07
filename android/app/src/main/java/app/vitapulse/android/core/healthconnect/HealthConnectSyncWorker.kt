package app.vitapulse.android.core.healthconnect

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.ListenableWorker.Result
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import app.vitapulse.android.VitaPulseApplication
import retrofit2.HttpException
import java.io.IOException
import java.util.concurrent.TimeUnit

class HealthConnectSyncWorker(
    context: Context,
    parameters: WorkerParameters,
) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val app = applicationContext as VitaPulseApplication
        if (!app.backendClient.isHealthDataSyncEnabled()) return Result.success()
        val repository = app.healthSyncRepository ?: return Result.success()

        repository.sync(HealthDataType.entries.toSet())

        return try {
            val hasMore = repository.uploadPendingBatch(app.backendClient::uploadHealthConnectSync)
            if (hasMore) Result.retry() else Result.success()
        } catch (_: IOException) {
            Result.retry()
        } catch (error: HttpException) {
            if (error.code() == 429 || error.code() >= 500) {
                Result.retry()
            } else {
                Result.failure(workDataOf("errorCode" to "BACKEND_REJECTED_HEALTH_DATA"))
            }
        } catch (_: IllegalStateException) {
            Result.failure(workDataOf("errorCode" to "HEALTH_DATA_UPLOAD_CONFIGURATION"))
        }
    }

    companion object {
        private const val PERIODIC_NAME = "health-connect-periodic-sync"
        private const val IMMEDIATE_NAME = "health-connect-immediate-sync"

        private val networkConstraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        fun schedulePeriodic(context: Context) {
            val request = PeriodicWorkRequestBuilder<HealthConnectSyncWorker>(6, TimeUnit.HOURS)
                .setConstraints(networkConstraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.MINUTES)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }

        fun cancelBackground(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(IMMEDIATE_NAME)
            WorkManager.getInstance(context).cancelUniqueWork(PERIODIC_NAME)
        }

        fun enqueueImmediate(context: Context) {
            val request = OneTimeWorkRequestBuilder<HealthConnectSyncWorker>()
                .setConstraints(networkConstraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.MINUTES)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                IMMEDIATE_NAME,
                ExistingWorkPolicy.KEEP,
                request,
            )
        }
    }
}
