package app.vitapulse.android.feature.reports

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import app.vitapulse.android.VitaPulseApplication
import app.vitapulse.android.core.device.ReportDetails
import app.vitapulse.android.core.device.ReportListItem
import kotlinx.coroutines.delay
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

@Composable
fun ReportsFeatureScreen(
    signedIn: Boolean,
    onSignIn: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val backend = (LocalContext.current.applicationContext as VitaPulseApplication).backendClient
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var reports by remember { mutableStateOf<List<ReportListItem>>(emptyList()) }
    var selectedId by remember { mutableStateOf<String?>(null) }
    var details by remember { mutableStateOf<ReportDetails?>(null) }
    var email by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var notice by remember { mutableStateOf<String?>(null) }

    suspend fun refreshReports() {
        loading = true
        error = null
        try {
            reports = backend.listReports()
        } catch (exception: CancellationException) {
            throw exception
        } catch (exception: Exception) {
            error = exception.message ?: "Reports could not be loaded."
        } finally {
            loading = false
        }
    }

    LaunchedEffect(signedIn) {
        if (signedIn) refreshReports()
    }
    LaunchedEffect(signedIn, reports.any { it.status !in setOf("COMPLETED", "FAILED", "CANCELLED") }) {
        if (signedIn && reports.any { it.status !in setOf("COMPLETED", "FAILED", "CANCELLED") }) {
            while (true) {
                delay(2_500)
                refreshReports()
            }
        }
    }

    LazyColumn(
        modifier = modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Column(Modifier.padding(top = 14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Reports & insights", style = MaterialTheme.typography.headlineSmall)
                Text("Source-linked summaries and recorded longitudinal comparisons.")
                if (!signedIn) {
                    Text("Sign in to create and view reports.")
                    Button(onClick = onSignIn) { Text("Sign in") }
                } else {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            enabled = !busy,
                            onClick = {
                                scope.launch {
                                    busy = true
                                    error = null
                                    notice = null
                                    try {
                                        val created = backend.createReport("WEEKLY_ATHLETE_REPORT")
                                        notice = "Report ${created.status.lowercase()}."
                                        refreshReports()
                                    } catch (exception: Exception) {
                                        error = exception.message ?: "The report could not be requested."
                                    } finally {
                                        busy = false
                                    }
                                }
                            },
                        ) { Text("Create weekly report") }
                        OutlinedButton(
                            enabled = !loading,
                            onClick = { scope.launch { refreshReports() } },
                        ) { Text("Refresh") }
                    }
                }
                if (loading && reports.isEmpty()) CircularProgressIndicator()
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                notice?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
            }
        }
        items(reports, key = { it.id }) { report ->
            Card(
                modifier = Modifier.fillMaxWidth().clickable {
                    selectedId = if (selectedId == report.id) null else report.id
                    details = null
                    if (selectedId == report.id) {
                        scope.launch {
                            try {
                                details = backend.report(report.id)
                                error = null
                            } catch (exception: Exception) {
                                error = exception.message ?: "Report details could not be loaded."
                            }
                        }
                    }
                },
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(report.title, style = MaterialTheme.typography.titleMedium)
                    Text("${report.reportType.replace('_', ' ')} · ${report.status.replace('_', ' ')}")
                    report.summary?.takeIf { it.isNotBlank() }?.let { Text(it) }
                    report.aiStatus?.let { Text("AI interpretation: ${it.replace('_', ' ').lowercase()}") }
                    report.emailStatus?.takeIf { it != "NOT_REQUESTED" }?.let {
                        Text("Email delivery: ${it.replace('_', ' ').lowercase()}")
                    }
                    if (selectedId == report.id && report.status == "COMPLETED") {
                        details?.let { detail ->
                            Text("Completeness: ${detail.dataCompleteness.replace('_', ' ')}")
                            Text(detail.factualSummary)
                            detail.longitudinalInsights.forEach { insight ->
                                Text(insight.statement)
                                Text("Sources: ${insight.sourceIds.joinToString()}", style = MaterialTheme.typography.bodySmall)
                            }
                            detail.dataGaps.forEach { Text("Data gap: $it", style = MaterialTheme.typography.bodySmall) }
                            detail.limitations.forEach { Text("Limitation: $it", style = MaterialTheme.typography.bodySmall) }
                            if (report.status == "COMPLETED") {
                                OutlinedTextField(
                                    value = email,
                                    onValueChange = { email = it },
                                    label = { Text("Recipient email") },
                                    singleLine = true,
                                    modifier = Modifier.fillMaxWidth(),
                                )
                                OutlinedButton(
                                    enabled = !busy && email.isNotBlank(),
                                    onClick = {
                                        scope.launch {
                                            busy = true
                                            error = null
                                            try {
                                                backend.emailReport(report.id, email.trim())
                                                notice = "Secure report link queued for email delivery."
                                            } catch (exception: CancellationException) {
                                                throw exception
                                            } catch (exception: Exception) {
                                                error = exception.message ?: "The report email could not be queued."
                                            } finally {
                                                busy = false
                                            }
                                        }
                                    },
                                ) { Text("Email secure link") }
                                OutlinedButton(
                                    enabled = !busy,
                                    onClick = {
                                        scope.launch {
                                            busy = true
                                            try {
                                                val url = backend.reportDownloadUrl(report.id)
                                                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                                            } catch (exception: CancellationException) {
                                                throw exception
                                            } catch (exception: Exception) {
                                                error = exception.message ?: "The PDF could not be opened."
                                            } finally {
                                                busy = false
                                            }
                                        }
                                    },
                                ) { Text("Open secure PDF") }
                            }
                        } ?: if (report.status == "COMPLETED") {
                            CircularProgressIndicator()
                        } else {
                            Text("Report processing: ${report.status.lowercase().replace('_', ' ')}")
                        }
                    }
                }
            }
        }
        if (signedIn && !loading && reports.isEmpty()) {
            item { Text("No reports yet. Create a weekly report to get started.") }
        }
    }
}
