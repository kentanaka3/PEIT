/// Wrapper around google_mlkit_text_recognition for processing receipt images
/// on-device into PEIT ParsedReceipt models.
library peit_mlkit_service;

import 'dart:io';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'models.dart';
import 'parser.dart';

class MLKitReceiptService {
  final TextRecognizer _recognizer;
  final ReceiptParser _parser;

  MLKitReceiptService({
    TextRecognitionScript script = TextRecognitionScript.latin,
    String defaultCurrency = 'MXN',
  })  : _recognizer = TextRecognizer(script: script),
        _parser = ReceiptParser(defaultCurrency: defaultCurrency);

  /// Process an image file from the device filesystem and parse it into a ParsedReceipt
  Future<ParsedReceipt> processImageFile(String filePath) async {
    final file = File(filePath);
    if (!file.existsSync()) {
      throw ArgumentError('Image file does not exist: $filePath');
    }

    final inputImage = InputImage.fromFilePath(filePath);
    final recognizedText = await _recognizer.processImage(inputImage);
    return parseRecognizedText(recognizedText);
  }

  /// Convert ML Kit RecognizedText into PEIT OCRTextBlock list and parse
  ParsedReceipt parseRecognizedText(RecognizedText recognizedText) {
    final blocks = <OCRTextBlock>[];

    for (final textBlock in recognizedText.blocks) {
      for (final line in textBlock.lines) {
        final rect = line.boundingBox;

        // BoundingBox with normalized fallback or pixel coordinates
        final bbox = BoundingBox(
          x: rect.left,
          y: rect.top,
          width: rect.width,
          height: rect.height,
        );

        blocks.add(OCRTextBlock(
          text: line.text,
          bbox: bbox,
          confidence: line.confidence ?? 1.0,
        ));
      }
    }

    return _parser.parseBlocks(blocks);
  }

  /// Close and dispose native ML Kit recognizer resources
  Future<void> dispose() async {
    await _recognizer.close();
  }
}

