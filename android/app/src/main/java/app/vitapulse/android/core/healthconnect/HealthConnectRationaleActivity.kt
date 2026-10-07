package app.vitapulse.android.core.healthconnect

import android.app.Activity
import android.os.Bundle
import android.widget.TextView

class HealthConnectRationaleActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(
            TextView(this).apply {
                text = "VitaPulse reads only the sleep, heart-rate, steps, exercise, and oxygen-saturation data you allow. " +
                    "These records support recovery, wellbeing, and activity context. Data is kept locally and can be " +
                    "synchronized securely to your VitaPulse account. You can revoke access in Health Connect at any time."
                textSize = 18f
                val padding = (24 * resources.displayMetrics.density).toInt()
                setPadding(padding, padding, padding, padding)
            },
        )
    }
}
