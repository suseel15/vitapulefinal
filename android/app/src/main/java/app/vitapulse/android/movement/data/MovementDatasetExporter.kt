package app.vitapulse.android.movement.data

import app.vitapulse.android.core.device.MovementSessionEntity
import app.vitapulse.android.core.device.MovementSampleEntity
import java.io.OutputStream
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

object MovementDatasetExporter {
    fun writeArchive(
        output: OutputStream,
        session: MovementSessionEntity,
        samplesNewestFirst: List<MovementSampleEntity>,
        pseudonymousAthleteId: String,
    ): Int {
        require(session.source == "LIVE_SENSOR") { "Only real sensor samples can be added to a training dataset." }
        require(samplesNewestFirst.size >= 30) { "Record at least three seconds of movement before exporting." }
        require(pseudonymousAthleteId.matches(Regex("^[A-Za-z0-9_-]{8,80}$"))) {
            "Dataset athlete identifier must be pseudonymous."
        }
        val exercise = exerciseClass(session.exerciseName)
        val samples = samplesNewestFirst
            .sortedBy { it.appTimestamp }
            .distinctBy { it.appTimestamp }
        require(samples.size >= 30) { "Record at least three seconds of movement before exporting." }
        require(samples.zipWithNext().all { (left, right) -> right.appTimestamp > left.appTimestamp }) {
            "Dataset samples must be ordered and have distinct timestamps."
        }
        val duration = samples.last().appTimestamp - samples.first().appTimestamp
        require(duration > 0) { "Dataset samples do not span a valid recording interval." }
        val measuredRate = (samples.size - 1) * 1000.0 / duration
        val zip = ZipOutputStream(output)
        zip.putNextEntry(ZipEntry("metadata.csv"))
        zip.write((
            "athlete_id,session_id,exercise,sensor_placement,device_id,sampling_rate_hz,source\n" +
                "$pseudonymousAthleteId,${session.id},$exercise,${session.sensorPlacement},${session.deviceIdentifier},$measuredRate,LIVE_SENSOR\n"
            ).toByteArray(Charsets.UTF_8))
        zip.closeEntry()
        zip.putNextEntry(ZipEntry("samples.csv"))
        zip.write("session_id,timestamp,ax,ay,az,gx,gy,gz\n".toByteArray(Charsets.UTF_8))
        samples.forEachIndexed { index, sample ->
            if (index > 0) zip.write("\n".toByteArray(Charsets.UTF_8))
            zip.write(
                "${session.id},${sample.appTimestamp},${sample.ax},${sample.ay},${sample.az},${sample.gx},${sample.gy},${sample.gz}"
                    .toByteArray(Charsets.UTF_8),
            )
        }
        zip.closeEntry()
        zip.putNextEntry(ZipEntry("labels.csv"))
        zip.write((
            "session_id,start_ms,end_ms,exercise,label_provenance\n" +
                "${session.id},${samples.first().appTimestamp},${samples.last().appTimestamp},$exercise,MANUAL\n"
            ).toByteArray(Charsets.UTF_8))
        zip.closeEntry()
        zip.finish()
        return samples.size
    }

    fun pseudonym(athleteId: String, installationSalt: String): String {
        require(athleteId.isNotBlank() && installationSalt.isNotBlank())
        return MessageDigest.getInstance("SHA-256")
            .digest("$installationSalt:$athleteId".toByteArray(Charsets.UTF_8))
            .take(16)
            .joinToString("") { "%02x".format(it) }
    }

    private fun exerciseClass(exerciseName: String): String {
        val normalized = exerciseName.lowercase().replace('-', ' ').replace('_', ' ')
        return when {
            "squat" in normalized -> "SQUAT"
            "calf raise" in normalized -> "CALF_RAISE"
            "sit to stand" in normalized -> "SIT_TO_STAND"
            "balance" in normalized -> "BALANCE"
            "leg raise" in normalized -> "LEG_RAISE"
            "bridge" in normalized -> "HAMSTRING_BRIDGE"
            else -> error("This Rehab exercise has no movement-dataset label mapping.")
        }
    }
}
