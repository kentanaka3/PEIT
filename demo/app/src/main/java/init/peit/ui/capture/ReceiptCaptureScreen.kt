package init.peit.ui.capture

import android.Manifest
import android.graphics.Bitmap
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Collections
import androidx.compose.material.icons.filled.PictureAsPdf
import androidx.compose.material.icons.filled.Segment
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import init.peit.data.ocr.OcrReceiptParser
import init.peit.data.ocr.PdfDocumentParser
import init.peit.data.ocr.ReceiptImageCropper
import init.peit.domain.model.ParsedReceipt
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

private suspend fun <T> awaitTask(task: com.google.android.gms.tasks.Task<T>): T = suspendCancellableCoroutine { continuation ->
    task.addOnSuccessListener { result ->
        if (continuation.isActive) {
            continuation.resume(result)
        }
    }.addOnFailureListener { exception ->
        if (continuation.isActive) {
            continuation.resumeWithException(exception)
        }
    }
}

@OptIn(ExperimentalPermissionsApi::class)
@Composable
fun ReceiptCaptureScreen(
    onReceiptParsed: (ParsedReceipt) -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    val cameraPermissionState = rememberPermissionState(Manifest.permission.CAMERA)
    val captureManager = remember { CameraCaptureManager(context) }
    val pdfParser = remember { PdfDocumentParser(context) }
    val ocrParser = remember { OcrReceiptParser() }
    val imageCropper = remember { ReceiptImageCropper() }

    var captureMode by remember { mutableStateOf(CaptureMode.SINGLE) }
    var isProcessingOcr by remember { mutableStateOf(false) }
    var ocrStatusText by remember { mutableStateOf("") }
    var ocrErrorText by remember { mutableStateOf<String?>(null) }

    val capturedBitmaps = remember { mutableStateListOf<Bitmap>() }

    DisposableEffect(captureManager) {
        onDispose {
            captureManager.unbind()
            capturedBitmaps.forEach(Bitmap::recycle)
            capturedBitmaps.clear()
        }
    }

    // Launcher for Gallery Picker
    val galleryLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia()
    ) { uri: Uri? ->
        uri?.let {
            scope.launch {
                isProcessingOcr = true
                ocrErrorText = null
                ocrStatusText = "Loading image from gallery..."
                var bitmap: Bitmap? = null
                try {
                    val loadedBitmap = withContext(Dispatchers.IO) {
                        val stream = context.contentResolver.openInputStream(it)
                            ?: throw IllegalStateException("Could not open the selected image")
                        stream.use { input ->
                            android.graphics.BitmapFactory.decodeStream(input)
                                ?: throw IllegalStateException("Could not decode the selected image")
                        }
                    }
                    bitmap = loadedBitmap
                    processBitmapsForOcr(listOf(loadedBitmap), ocrParser, imageCropper, onReceiptParsed) { text ->
                        ocrStatusText = text
                    }
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (error: Exception) {
                    ocrErrorText = "OCR failed: ${error.localizedMessage.orEmpty()}"
                } finally {
                    bitmap?.recycle()
                    isProcessingOcr = false
                }
            }
        }
    }

    // Launcher for Document / PDF Picker
    val documentLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        uri?.let {
            scope.launch {
                isProcessingOcr = true
                ocrErrorText = null
                ocrStatusText = "Rendering PDF pages..."
                var pdfBitmaps: List<Bitmap> = emptyList()
                try {
                    pdfBitmaps = pdfParser.renderPdfPagesToBitmaps(it)
                    check(pdfBitmaps.isNotEmpty()) { "Selected PDF contains no pages" }
                    processBitmapsForOcr(pdfBitmaps, ocrParser, imageCropper, onReceiptParsed) { text ->
                        ocrStatusText = text
                    }
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (error: Exception) {
                    ocrErrorText = "OCR failed: ${error.localizedMessage.orEmpty()}"
                } finally {
                    pdfBitmaps.forEach(Bitmap::recycle)
                    isProcessingOcr = false
                }
            }
        }
    }

    Box(modifier = modifier.fillMaxSize().background(Color.Black)) {
        if (cameraPermissionState.status.isGranted) {
            AndroidView(
                factory = { ctx ->
                    val previewView = PreviewView(ctx)
                    scope.launch {
                        try {
                            val provider = captureManager.getCameraProvider()
                            captureManager.bindCamera(
                                lifecycleOwner = ctx as androidx.lifecycle.LifecycleOwner,
                                cameraProvider = provider,
                                surfaceProvider = previewView.surfaceProvider
                            )
                        } catch (error: Exception) {
                            ocrErrorText = "Camera unavailable: ${error.localizedMessage.orEmpty()}"
                        }
                    }
                    previewView
                },
                modifier = Modifier.fillMaxSize()
            )
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Text(
                    text = "Camera Permission Required",
                    style = MaterialTheme.typography.titleMedium,
                    color = Color.White
                )
                Spacer(modifier = Modifier.height(16.dp))
                Button(onClick = { cameraPermissionState.launchPermissionRequest() }) {
                    Text("Grant Camera Permission")
                }
            }
        }

        // Overlay Controls
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 16.dp),
                shape = RoundedCornerShape(18.dp),
                colors = CardDefaults.cardColors(
                    containerColor = Color(0xCC112B35),
                    contentColor = Color.White
                )
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text(
                        text = "Capture a receipt",
                        style = MaterialTheme.typography.titleMedium,
                        color = Color.White
                    )
                    Text(
                        text = "Images are processed on this device.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.86f)
                    )
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 4.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        FilterChip(
                            selected = captureMode == CaptureMode.SINGLE,
                            enabled = !isProcessingOcr,
                            onClick = { captureMode = CaptureMode.SINGLE },
                            label = { Text("Single page", maxLines = 1, softWrap = false) }
                        )
                        FilterChip(
                            selected = captureMode == CaptureMode.MULTI_BURST,
                            enabled = !isProcessingOcr,
                            onClick = { captureMode = CaptureMode.MULTI_BURST },
                            label = { Text("Multi-page", maxLines = 1, softWrap = false) }
                        )
                    }
                }
            }

            // Processing Indicator
            if (isProcessingOcr) {
                Card(
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(24.dp))
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = ocrStatusText,
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            }
            ocrErrorText?.let { message ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .align(Alignment.CenterHorizontally),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer
                    )
                ) {
                    Text(
                        text = message,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            // Burst Preview Strip
            if (capturedBitmaps.isNotEmpty()) {
                LazyRow(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 8.dp)
                ) {
                    items(capturedBitmaps) { bitmap ->
                        Card(
                            modifier = Modifier
                                .size(60.dp)
                                .padding(end = 8.dp)
                        ) {
                            Image(
                                bitmap = bitmap.asImageBitmap(),
                                contentDescription = "Captured page",
                                modifier = Modifier.fillMaxSize()
                            )
                        }
                    }
                }
            }

            // Bottom Actions Bar (Gallery, Capture Button, Document Picker)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 24.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Gallery Launcher
                IconButton(
                    enabled = !isProcessingOcr,
                    onClick = {
                        galleryLauncher.launch(
                            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                        )
                    },
                    modifier = Modifier
                        .background(Color.White.copy(alpha = 0.2f), CircleShape)
                        .size(48.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Collections,
                        contentDescription = "Gallery Picker",
                        tint = Color.White
                    )
                }

                // Shutter / Capture Button
                IconButton(
                    enabled = !isProcessingOcr,
                    onClick = {
                        if (cameraPermissionState.status.isGranted) {
                            scope.launch {
                                isProcessingOcr = true
                                ocrErrorText = null
                                var bitmap: Bitmap? = null
                                var retainedForBurst = false
                                var photoFile: java.io.File? = null
                                try {
                                    val capturedPhotoFile = captureManager.takePhoto()
                                    photoFile = capturedPhotoFile
                                    val capturedBitmap = captureManager.loadBitmapFromFile(capturedPhotoFile)
                                    bitmap = capturedBitmap
                                    if (captureMode == CaptureMode.SINGLE) {
                                        ocrStatusText = "Processing OCR..."
                                        processBitmapsForOcr(
                                            listOf(capturedBitmap),
                                            ocrParser,
                                            imageCropper,
                                            onReceiptParsed
                                        ) { text -> ocrStatusText = text }
                                    } else {
                                        capturedBitmaps.add(capturedBitmap)
                                        retainedForBurst = true
                                    }
                                } catch (cancelled: CancellationException) {
                                    throw cancelled
                                } catch (error: Exception) {
                                    ocrErrorText = "Capture/OCR failed: ${error.localizedMessage.orEmpty()}"
                                } finally {
                                    if (!retainedForBurst) bitmap?.recycle()
                                    photoFile?.delete()
                                    isProcessingOcr = false
                                }
                            }
                        } else {
                            cameraPermissionState.launchPermissionRequest()
                        }
                    },
                    modifier = Modifier
                        .background(Color.White, CircleShape)
                        .size(72.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.CameraAlt,
                        contentDescription = "Capture Photo",
                        tint = Color.Black,
                        modifier = Modifier.size(36.dp)
                    )
                }

                // PDF / Document Launcher
                IconButton(
                    enabled = !isProcessingOcr,
                    onClick = {
                        documentLauncher.launch(arrayOf("application/pdf"))
                    },
                    modifier = Modifier
                        .background(Color.White.copy(alpha = 0.2f), CircleShape)
                        .size(48.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.PictureAsPdf,
                        contentDescription = "Document Picker",
                        tint = Color.White
                    )
                }
            }

            // Finish Multi-Burst Action
            if (captureMode == CaptureMode.MULTI_BURST && capturedBitmaps.isNotEmpty()) {
                Button(
                    enabled = !isProcessingOcr,
                    onClick = {
                        scope.launch {
                            isProcessingOcr = true
                            ocrErrorText = null
                            ocrStatusText = "Processing multi-page burst OCR..."
                            val pages = capturedBitmaps.toList()
                            var completed = false
                            try {
                                processBitmapsForOcr(pages, ocrParser, imageCropper, onReceiptParsed) { text ->
                                    ocrStatusText = text
                                }
                                completed = true
                            } catch (cancelled: CancellationException) {
                                throw cancelled
                            } catch (error: Exception) {
                                ocrErrorText = "Capture/OCR failed: ${error.localizedMessage.orEmpty()}"
                            } finally {
                                if (completed) {
                                    pages.forEach(Bitmap::recycle)
                                    capturedBitmaps.clear()
                                }
                                isProcessingOcr = false
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.Segment, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Process ${capturedBitmaps.size} Captured Pages")
                }
            }
        }
    }
}

private suspend fun processBitmapsForOcr(
    bitmaps: List<Bitmap>,
    ocrParser: OcrReceiptParser,
    imageCropper: ReceiptImageCropper,
    onReceiptParsed: (ParsedReceipt) -> Unit,
    updateStatus: (String) -> Unit
) = withContext(Dispatchers.Default) {
    val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    val parsedReceipts = mutableListOf<ParsedReceipt>()
    val temporarySnippets = mutableListOf<Bitmap>()
    try {
        for ((index, bitmap) in bitmaps.withIndex()) {
            withContext(Dispatchers.Main) {
                updateStatus("Running OCR on page ${index + 1} of ${bitmaps.size}...")
            }
            val inputImage = InputImage.fromBitmap(bitmap, 0)
            val task = recognizer.process(inputImage)
            val mlKitText = awaitTask(task)
            check(mlKitText.text.isNotBlank()) { "No text was detected on page ${index + 1}" }
            val parsed = ocrParser.parse(mlKitText)
            val itemsWithSnippets = parsed.items.map { item ->
                if (item.boundingBox != null) {
                    val snippet = imageCropper.cropSnippetWithDescenderPadding(bitmap, item.boundingBox)
                    if (snippet != null) temporarySnippets.add(snippet)
                    item.copy(croppedSnippetBitmap = snippet)
                } else item
            }
            parsedReceipts.add(parsed.copy(items = itemsWithSnippets))
        }

        check(parsedReceipts.size == bitmaps.size) { "OCR did not complete every selected page" }
        check(parsedReceipts.isNotEmpty()) { "No receipt pages were processed" }
        // Combine pages if multi-burst
        val first = parsedReceipts.first()
        val combinedItems = parsedReceipts.flatMap { it.items }
        val combinedTax = parsedReceipts.sumOf { it.tax }
        val combinedDiscount = parsedReceipts.sumOf { it.discount }
        val combinedFee = parsedReceipts.sumOf { it.fee }
        val combinedDeposit = parsedReceipts.sumOf { it.deposit }
        val combinedPaidTotal = parsedReceipts.last().paidTotal.let {
            if (it > 0) it else parsedReceipts.sumOf { p -> p.paidTotal }
        }

        val finalParsed = first.copy(
            items = combinedItems,
            tax = combinedTax,
            discount = combinedDiscount,
            fee = combinedFee,
            deposit = combinedDeposit,
            paidTotal = combinedPaidTotal
        )

        withContext(Dispatchers.Main) {
            onReceiptParsed(finalParsed)
        }
    } catch (error: Exception) {
        temporarySnippets.forEach(Bitmap::recycle)
        throw error
    } finally {
        recognizer.close()
    }
}
