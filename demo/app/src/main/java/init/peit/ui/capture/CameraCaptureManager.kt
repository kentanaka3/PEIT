package init.peit.ui.capture

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executor
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

enum class CaptureMode {
    SINGLE,
    MULTI_BURST
}

class CameraCaptureManager(private val context: Context) {

    private val mainExecutor: Executor = ContextCompat.getMainExecutor(context)
    private var boundProvider: ProcessCameraProvider? = null
    var imageCapture: ImageCapture? = null
        private set

    suspend fun getCameraProvider(): ProcessCameraProvider = suspendCancellableCoroutine { continuation ->
        val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
        cameraProviderFuture.addListener({
            try {
                if (continuation.isActive) {
                    continuation.resume(cameraProviderFuture.get())
                }
            } catch (e: Exception) {
                if (continuation.isActive) {
                    continuation.resumeWithException(e)
                }
            }
        }, mainExecutor)
    }

    fun bindCamera(
        lifecycleOwner: LifecycleOwner,
        cameraProvider: ProcessCameraProvider,
        surfaceProvider: Preview.SurfaceProvider
    ) {
        val preview = Preview.Builder().build().also {
            it.surfaceProvider = surfaceProvider
        }

        imageCapture = ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .build()

        val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

        try {
            cameraProvider.unbindAll()
            cameraProvider.bindToLifecycle(
                lifecycleOwner,
                cameraSelector,
                preview,
                imageCapture
            )
            boundProvider = cameraProvider
        } catch (e: Exception) {
            throw IllegalStateException("Could not bind the camera", e)
        }
    }

    fun unbind() {
        boundProvider?.unbindAll()
        boundProvider = null
        imageCapture = null
    }

    suspend fun takePhoto(): File = suspendCancellableCoroutine { continuation ->
        val capture = imageCapture
        if (capture == null) {
            if (continuation.isActive) {
                continuation.resumeWithException(IllegalStateException("Camera not initialized"))
            }
            return@suspendCancellableCoroutine
        }

        val photoFile = createTempImageFile(context)
        continuation.invokeOnCancellation { photoFile.delete() }
        val outputOptions = ImageCapture.OutputFileOptions.Builder(photoFile).build()

        capture.takePicture(
            outputOptions,
            mainExecutor,
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                    if (continuation.isActive) {
                        continuation.resume(photoFile)
                    }
                }

                override fun onError(exc: ImageCaptureException) {
                    photoFile.delete()
                    if (continuation.isActive) {
                        continuation.resumeWithException(exc)
                    }
                }
            }
        )
    }

    fun loadBitmapFromFile(file: File): Bitmap {
        return BitmapFactory.decodeFile(file.absolutePath)
            ?: throw IOException("Could not decode captured image")
    }

    companion object {
        fun createTempImageFile(context: Context): File {
            val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val storageDir = context.cacheDir
            return File.createTempFile("JPEG_${timeStamp}_", ".jpg", storageDir)
        }
    }
}
