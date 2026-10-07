/// Background isolate worker for slicing receipt image bounding boxes
/// using package:image without blocking the UI thread.
library peit_snippet_cropper;

import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:image/image.dart' as img;
import 'models.dart';

class CropTaskRequest {
  final String id;
  final BoundingBox bbox;

  const CropTaskRequest({required this.id, required this.bbox});

  Map<String, dynamic> toMap() => {
    'id': id,
    'x': bbox.x,
    'y': bbox.y,
    'width': bbox.width,
    'height': bbox.height,
  };

  factory CropTaskRequest.fromMap(Map<String, dynamic> map) => CropTaskRequest(
    id: map['id'] as String,
    bbox: BoundingBox(
      x: (map['x'] as num).toDouble(),
      y: (map['y'] as num).toDouble(),
      width: (map['width'] as num).toDouble(),
      height: (map['height'] as num).toDouble(),
    ),
  );
}

class SnippetCropper {
  /// Crop multiple bounding boxes in a background isolate using `compute`.
  /// Takes image file path and a list of CropTaskRequests.
  /// Returns a map of ID -> PNG/JPEG image bytes.
  static Future<Map<String, Uint8List>> cropSnippetsFromFile({
    required String imagePath,
    required List<CropTaskRequest> requests,
    double padYFactor = 0.15,
    double padXFactor = 0.05,
  }) async {
    final file = File(imagePath);
    if (!file.existsSync()) return {};
    final fileBytes = await file.readAsBytes();

    return compute(_isolateCropWorker, {
      'imageBytes': fileBytes,
      'requests': requests.map((r) => r.toMap()).toList(),
      'padYFactor': padYFactor,
      'padXFactor': padXFactor,
    });
  }

  /// Crop multiple bounding boxes from in-memory image bytes in a background isolate.
  static Future<Map<String, Uint8List>> cropSnippetsFromBytes({
    required Uint8List imageBytes,
    required List<CropTaskRequest> requests,
    double padYFactor = 0.15,
    double padXFactor = 0.05,
  }) async {
    return compute(_isolateCropWorker, {
      'imageBytes': imageBytes,
      'requests': requests.map((r) => r.toMap()).toList(),
      'padYFactor': padYFactor,
      'padXFactor': padXFactor,
    });
  }

  /// Top-level worker executed in background isolate
  static Map<String, Uint8List> _isolateCropWorker(Map<String, dynamic> params) {
    final Uint8List imageBytes = params['imageBytes'] as Uint8List;
    final List<dynamic> rawRequests = params['requests'] as List<dynamic>;
    final double padYFactor = (params['padYFactor'] as num?)?.toDouble() ?? 0.15;
    final double padXFactor = (params['padXFactor'] as num?)?.toDouble() ?? 0.05;

    final decoded = img.decodeImage(imageBytes);
    if (decoded == null) return {};

    final imgW = decoded.width;
    final imgH = decoded.height;
    final results = <String, Uint8List>{};

    for (final raw in rawRequests) {
      final reqMap = raw as Map<String, dynamic>;
      final id = reqMap['id'] as String;
      double rx = (reqMap['x'] as num).toDouble();
      double ry = (reqMap['y'] as num).toDouble();
      double rw = (reqMap['width'] as num).toDouble();
      double rh = (reqMap['height'] as num).toDouble();

      // Convert normalized [0, 1] coordinates to pixel coordinates if < 1.5
      if (rx <= 1.0 && ry <= 1.0 && rw <= 1.0 && rh <= 1.0) {
        rx *= imgW;
        ry *= imgH;
        rw *= imgW;
        rh *= imgH;
      }

      // Descender safety padding (e.g. +15% height, +5% width)
      final padY = rh * padYFactor;
      final padX = rw * padXFactor;

      final startX = (rx - padX).clamp(0.0, (imgW - 1).toDouble()).toInt();
      final startY = (ry - padY).clamp(0.0, (imgH - 1).toDouble()).toInt();
      final width = (rw + padX * 2.0).clamp(1.0, (imgW - startX).toDouble()).toInt();
      final height = (rh + padY * 2.0).clamp(1.0, (imgH - startY).toDouble()).toInt();

      final cropped = img.copyCrop(
        decoded,
        x: startX,
        y: startY,
        width: width,
        height: height,
      );

      final pngBytes = Uint8List.fromList(img.encodePng(cropped));
      results[id] = pngBytes;
    }

    return results;
  }
}

