package app.vitapulse.android.feature.wellbeing.analysis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CameraWellbeingFeatureExtractorTest {
    @Test
    fun returnsCaptureQualityFromValidFrameProportion() {
        val observations = (0 until 10).map { index ->
            centeredFrame(index * 100L).copy(faceCount = if (index < 8) 1 else 0)
        }

        val result = CameraWellbeingFeatureExtractor.extract(observations)

        assertEquals(0.8, result.validFrameRatio, 0.0001)
        assertEquals("GOOD", result.captureQuality)
        assertEquals(8, result.faceDetectedFrames)
    }

    @Test
    fun doesNotFabricateEyeOrSmileFeaturesWhenDetectorDoesNotProvideThem() {
        val result = CameraWellbeingFeatureExtractor.extract(
            (0 until 4).map { centeredFrame(it * 100L) },
        )

        assertNull(result.eyeObservationRatio)
        assertNull(result.smileObservationRatio)
    }

    @Test
    fun precheckRejectsMissingMultipleSmallOffCenterAndDarkFaces() {
        assertEquals(FacePrecheck.NO_FACE, CameraWellbeingFeatureExtractor.precheck(FrameObservation(0, 0)))
        assertEquals(FacePrecheck.MULTIPLE_FACES, CameraWellbeingFeatureExtractor.precheck(centeredFrame(0).copy(faceCount = 2)))
        assertEquals(FacePrecheck.FACE_TOO_SMALL, CameraWellbeingFeatureExtractor.precheck(centeredFrame(0).copy(widthFraction = 0.1)))
        assertEquals(FacePrecheck.FACE_OFF_CENTER, CameraWellbeingFeatureExtractor.precheck(centeredFrame(0).copy(centerX = 0.9)))
        assertEquals(FacePrecheck.POOR_LIGHTING, CameraWellbeingFeatureExtractor.precheck(centeredFrame(0).copy(averageLuma = 10.0)))
        assertEquals(FacePrecheck.BLURRY, CameraWellbeingFeatureExtractor.precheck(centeredFrame(0).copy(sharpness = 0.5)))
        assertEquals(
            FacePrecheck.FACE_NOT_FACING_CAMERA,
            CameraWellbeingFeatureExtractor.precheck(centeredFrame(0).copy(headEulerY = 35.0)),
        )
    }

    @Test
    fun unstablePositionIsDescribedAsVariableWithoutPsychologicalInterpretation() {
        val observations = listOf(
            centeredFrame(0),
            centeredFrame(100).copy(centerX = 0.7),
            centeredFrame(200).copy(centerX = 0.3),
        )

        val result = CameraWellbeingFeatureExtractor.extract(observations)

        assertEquals("VARIABLE", result.facePositionStability)
        assertTrue(result.headMovementMagnitude != null)
        assertEquals("GOOD", result.captureQuality)
    }

    private fun centeredFrame(timestamp: Long) = FrameObservation(
        timestampMs = timestamp,
        faceCount = 1,
        centerX = 0.5,
        centerY = 0.5,
        widthFraction = 0.35,
        averageLuma = 120.0,
        sharpness = 10.0,
    )
}
