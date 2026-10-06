package app.vitapulse.android.feature.wellbeing.camera

import android.graphics.Rect
import android.os.SystemClock
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.Face
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetector
import com.google.mlkit.vision.face.FaceDetectorOptions
import app.vitapulse.android.feature.wellbeing.analysis.FrameObservation
import java.nio.ByteBuffer
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.max
import kotlin.math.min

class FaceDetectionAnalyzer(
    private val onObservation: (FrameObservation) -> Unit,
    private val onFailure: (Exception) -> Unit,
) : ImageAnalysis.Analyzer, AutoCloseable {
    private val detector: FaceDetector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_ALL)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_NONE)
            .setContourMode(FaceDetectorOptions.CONTOUR_MODE_NONE)
            .setMinFaceSize(0.15f)
            .build(),
    )
    private val processing = AtomicBoolean(false)
    private val closed = AtomicBoolean(false)
    private var lastAnalyzedAtMs = 0L

    override fun analyze(image: ImageProxy) {
        val now = SystemClock.elapsedRealtime()
        if (closed.get() || now - lastAnalyzedAtMs < FRAME_INTERVAL_MS || !processing.compareAndSet(false, true)) {
            image.close()
            return
        }
        lastAnalyzedAtMs = now
        val mediaImage = image.image
        if (mediaImage == null) {
            processing.set(false)
            image.close()
            return
        }
        val lumaPlane = image.planes.firstOrNull()
        val luma = lumaPlane?.buffer?.let(::averageLuma)
        val sharpness = lumaPlane?.let {
            estimateSharpness(it.buffer, image.width, image.height, it.rowStride, it.pixelStride)
        }
        val input = InputImage.fromMediaImage(mediaImage, image.imageInfo.rotationDegrees)
        try {
            detector.process(input)
                .addOnSuccessListener { faces ->
                    if (!closed.get()) {
                        onObservation(
                            faces.toObservation(
                                image.width,
                                image.height,
                                image.imageInfo.rotationDegrees,
                                luma,
                                sharpness,
                            ),
                        )
                    }
                }
                .addOnFailureListener { error ->
                    if (!closed.get()) onFailure(error)
                }
                .addOnCompleteListener {
                    processing.set(false)
                    image.close()
                }
        } catch (error: Exception) {
            processing.set(false)
            image.close()
            if (!closed.get()) onFailure(error)
        }
    }

    override fun close() {
        if (closed.compareAndSet(false, true)) detector.close()
    }

    private fun List<Face>.toObservation(
        width: Int,
        height: Int,
        rotation: Int,
        luma: Double?,
        sharpness: Double?,
    ): FrameObservation {
        val face = singleOrNull()
        val rotated = rotation == 90 || rotation == 270
        val viewWidth = if (rotated) height else width
        val viewHeight = if (rotated) width else height
        val bounds: Rect? = face?.boundingBox
        return FrameObservation(
            timestampMs = System.currentTimeMillis(),
            faceCount = size,
            centerX = bounds?.centerX()?.toDouble()?.div(viewWidth),
            centerY = bounds?.centerY()?.toDouble()?.div(viewHeight),
            widthFraction = bounds?.width()?.toDouble()?.div(viewWidth),
            headEulerX = face?.headEulerAngleX?.toDouble(),
            headEulerY = face?.headEulerAngleY?.toDouble(),
            headEulerZ = face?.headEulerAngleZ?.toDouble(),
            leftEyeOpenProbability = face?.leftEyeOpenProbability?.toDouble(),
            rightEyeOpenProbability = face?.rightEyeOpenProbability?.toDouble(),
            smileProbability = face?.smilingProbability?.toDouble(),
            averageLuma = luma,
            sharpness = sharpness,
        )
    }

    private fun estimateSharpness(
        buffer: ByteBuffer,
        width: Int,
        height: Int,
        rowStride: Int,
        pixelStride: Int,
    ): Double? {
        if (width < 2 || height < 1) return null
        val copy = buffer.duplicate()
        var total = 0.0
        var count = 0
        val stepX = (width / 64).coerceAtLeast(1)
        val stepY = (height / 48).coerceAtLeast(1)
        for (y in 0 until height step stepY) {
            for (x in 0 until width - 1 step stepX) {
                val index = y * rowStride + x * pixelStride
                val nextIndex = y * rowStride + (x + 1) * pixelStride
                if (nextIndex >= copy.limit()) continue
                val current = copy.get(index).toInt() and 0xff
                val next = copy.get(nextIndex).toInt() and 0xff
                total += kotlin.math.abs(next - current)
                count++
            }
        }
        return if (count == 0) null else total / count
    }

    private fun averageLuma(buffer: ByteBuffer): Double? {
        val copy = buffer.duplicate()
        if (!copy.hasRemaining()) return null
        val sampleCount = min(copy.remaining(), MAX_LUMA_SAMPLES)
        val step = max(1, copy.remaining() / sampleCount)
        var total = 0L
        var count = 0
        while (copy.hasRemaining() && count < sampleCount) {
            total += copy.get().toInt() and 0xff
            count++
            repeat(step - 1) { if (copy.hasRemaining()) copy.get() }
        }
        return if (count == 0) null else total.toDouble() / count
    }

    private companion object {
        const val FRAME_INTERVAL_MS = 250L
        const val MAX_LUMA_SAMPLES = 256
    }
}
