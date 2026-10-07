package app.vitapulse.android.core.device

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class Esp32SensorReadingTest {
    @Test
    fun uploadedExerciseFirmwareResponsePreservesCounterAndMotionFields() {
        val response = Gson().fromJson(
            """
                {
                  "mpu": true,
                  "ax": 0.12,
                  "ay": -0.24,
                  "az": 0.98,
                  "gx": 10.5,
                  "gy": -4.25,
                  "gz": 0.0,
                  "exercise": "Bicep Curl",
                  "reps": 3,
                  "phase": "UP",
                  "motion": "ACTIVE"
                }
            """.trimIndent(),
            Esp32SensorResponse::class.java,
        )

        assertEquals(3, response.reps)
        assertEquals("Bicep Curl", response.exercise)
        assertEquals("UP", response.phase)
        assertEquals("ACTIVE", response.motion)
    }

    @Test
    fun olderSensorResponsesRemainCompatibleWithoutExerciseFields() {
        val response = Gson().fromJson(
            """{"mpu":true,"ax":0.0,"ay":0.0,"az":1.0,"gx":0.0,"gy":0.0,"gz":0.0}""",
            Esp32SensorResponse::class.java,
        )

        assertNull(response.reps)
        assertNull(response.exercise)
        assertNull(response.phase)
        assertNull(response.motion)
    }

    @Test
    fun exerciseOptionsMatchTheUploadedFirmwareIndicesAndNames() {
        assertEquals(10, ESP32_EXERCISES.size)
        assertEquals(listOf(0, 1, 2, 3, 4, 5, 6, 7, 8, 9), ESP32_EXERCISES.map { it.index })
        assertEquals("Bicep Curl", ESP32_EXERCISES.first().name)
        assertEquals("Tricep Kickback", ESP32_EXERCISES.last().name)
    }
}
