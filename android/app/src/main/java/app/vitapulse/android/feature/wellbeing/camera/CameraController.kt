package app.vitapulse.android.feature.wellbeing.camera

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.util.Size
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class CameraController(
    context: Context,
    private val lifecycleOwner: LifecycleOwner,
    private val onObservation: (app.vitapulse.android.feature.wellbeing.analysis.FrameObservation) -> Unit,
    private val onFailure: (Exception) -> Unit,
) : AutoCloseable {
    private val appContext = context.applicationContext
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private val released = AtomicBoolean(false)
    private var provider: ProcessCameraProvider? = null
    private var analysis: ImageAnalysis? = null
    private var analyzer: FaceDetectionAnalyzer? = null
    private var preview: Preview? = null

    fun start(previewView: PreviewView) {
        if (ContextCompat.checkSelfPermission(appContext, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            onFailure(SecurityException("Camera permission is required to start this assessment."))
            return
        }
        val providerFuture = ProcessCameraProvider.getInstance(appContext)
        providerFuture.addListener(
            {
                if (released.get()) return@addListener
                try {
                    val cameraProvider = providerFuture.get()
                    provider = cameraProvider
                    val cameraPreview = Preview.Builder().build().also {
                        it.surfaceProvider = previewView.surfaceProvider
                    }
                    val imageAnalysis = ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .setTargetResolution(Size(640, 480))
                        .build()
                    val faceAnalyzer = FaceDetectionAnalyzer(onObservation, onFailure)
                    preview = cameraPreview
                    analysis = imageAnalysis
                    analyzer = faceAnalyzer
                    imageAnalysis.setAnalyzer(executor, faceAnalyzer)
                    cameraProvider.bindToLifecycle(
                        lifecycleOwner,
                        CameraSelector.DEFAULT_FRONT_CAMERA,
                        cameraPreview,
                        imageAnalysis,
                    )
                } catch (error: Exception) {
                    onFailure(error)
                    close()
                }
            },
            ContextCompat.getMainExecutor(appContext),
        )
    }

    override fun close() {
        if (released.compareAndSet(false, true)) {
            analysis?.clearAnalyzer()
            analyzer?.close()
            provider?.let { cameraProvider ->
                val useCases = listOfNotNull(preview, analysis)
                if (useCases.isNotEmpty()) cameraProvider.unbind(*useCases.toTypedArray())
            }
            executor.shutdown()
            analysis = null
            analyzer = null
            preview = null
            provider = null
        }
    }
}
