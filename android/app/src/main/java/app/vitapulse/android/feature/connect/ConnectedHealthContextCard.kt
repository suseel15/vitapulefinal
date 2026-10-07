package app.vitapulse.android.feature.connect

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import app.vitapulse.android.VitaPulseApplication
import app.vitapulse.android.core.healthconnect.HealthContextMetric
import app.vitapulse.android.core.healthconnect.RecoveryDataProvider
import app.vitapulse.android.core.healthconnect.RecoveryDataSnapshot
import app.vitapulse.android.core.healthconnect.RoomRecoveryDataProvider
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
fun ConnectedHealthContextCard(
    modifier: Modifier = Modifier,
    title: String = "Health Connect context",
    onOpenConnect: () -> Unit = {},
) {
    val app = LocalContext.current.applicationContext as VitaPulseApplication
    val provider: RecoveryDataProvider = remember(app) {
        RoomRecoveryDataProvider(app.healthDataDatabase.healthDataDao())
    }
    val snapshot by provider.observeRecoveryContext()
        .collectAsStateWithLifecycle(initialValue = RecoveryDataSnapshot())

    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(title, style = MaterialTheme.typography.titleLarge)
            val metrics = listOfNotNull(snapshot.sleep, snapshot.activity, snapshot.heartRate)
            if (metrics.isEmpty()) {
                Text(
                    "No recent Health Connect records are available. Connect a source and sync to show your data here.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                Button(onClick = onOpenConnect) { Text("Open Connect") }
            } else {
                metrics.forEach { metric -> HealthContextMetricRow(metric) }
                Text(
                    "These are connected measurements, not a medical assessment or recovery score.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

@Composable
private fun HealthContextMetricRow(metric: HealthContextMetric) {
    val formatter = remember {
        DateTimeFormatter.ofPattern("d MMM, HH:mm", Locale.getDefault())
            .withZone(ZoneId.systemDefault())
    }
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(metric.label, style = MaterialTheme.typography.titleSmall)
            Text(metric.value, style = MaterialTheme.typography.bodyMedium)
        }
        Text(
            "Record ${formatTime(metric.recordAtMs, formatter)} · Synced ${formatTime(metric.syncedAtMs, formatter)}",
            style = MaterialTheme.typography.bodySmall,
        )
        Text(
            "Source: ${metric.source} · ${metric.sourceApplication}",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

private fun formatTime(timeMs: Long, formatter: DateTimeFormatter): String =
    formatter.format(Instant.ofEpochMilli(timeMs))
