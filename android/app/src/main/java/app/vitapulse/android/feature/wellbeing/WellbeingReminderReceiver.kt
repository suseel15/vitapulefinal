package app.vitapulse.android.feature.wellbeing

import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import app.vitapulse.android.MainActivity
import app.vitapulse.android.R
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId

class WellbeingReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Wellbeing reminders", NotificationManager.IMPORTANCE_DEFAULT),
        )
        val openApp = PendingIntent.getActivity(
            context,
            NOTIFICATION_ID,
            Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        manager.notify(
            NOTIFICATION_ID,
            Notification.Builder(context, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_vitapulse)
                .setContentTitle("How are you feeling today?")
                .setContentText("Take a moment for your optional athlete wellbeing check-in.")
                .setContentIntent(openApp)
                .setAutoCancel(true)
                .build(),
        )
    }

    companion object {
        private const val CHANNEL_ID = "wellbeing-checkin"
        private const val NOTIFICATION_ID = 6031
        private const val REQUEST_ID = 6032

        fun schedule(context: Context, time: LocalTime) {
            val now = LocalDateTime.now()
            var next = now.toLocalDate().atTime(time)
            if (!next.isAfter(now)) next = next.plusDays(1)
            val triggerAt = next.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
            val alarmManager = context.getSystemService(AlarmManager::class.java)
            alarmManager.setInexactRepeating(
                AlarmManager.RTC_WAKEUP,
                triggerAt,
                AlarmManager.INTERVAL_DAY,
                pendingIntent(context),
            )
        }

        fun cancel(context: Context) {
            context.getSystemService(AlarmManager::class.java).cancel(pendingIntent(context))
        }

        private fun pendingIntent(context: Context) = PendingIntent.getBroadcast(
            context,
            REQUEST_ID,
            Intent(context, WellbeingReminderReceiver::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }
}
