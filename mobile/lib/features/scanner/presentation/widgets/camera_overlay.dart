import 'package:flutter/material.dart';

class CameraOverlay extends StatelessWidget {
  const CameraOverlay({super.key});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _OverlayPainter());
  }
}

class _OverlayPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final outer = Rect.fromLTWH(0, 0, size.width, size.height);
    final frameW = size.width * 0.85;
    final frameH = frameW * 1.4;
    final frameL = (size.width - frameW) / 2;
    final frameT = (size.height - frameH) / 2;
    final frame = Rect.fromLTWH(frameL, frameT, frameW, frameH);

    final dimPaint = Paint()..color = Colors.black54;
    final framePath = Path()
      ..addRect(outer)
      ..addRRect(RRect.fromRectAndRadius(frame, const Radius.circular(12)))
      ..fillType = PathFillType.evenOdd;
    canvas.drawPath(framePath, dimPaint);

    final cornerPaint = Paint()
      ..color = Colors.white
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    const cornerLen = 24.0;
    const r = 12.0;

    // Top-left
    canvas.drawLine(Offset(frameL + r, frameT), Offset(frameL + r + cornerLen, frameT), cornerPaint);
    canvas.drawLine(Offset(frameL, frameT + r), Offset(frameL, frameT + r + cornerLen), cornerPaint);
    // Top-right
    canvas.drawLine(Offset(frame.right - r - cornerLen, frameT), Offset(frame.right - r, frameT), cornerPaint);
    canvas.drawLine(Offset(frame.right, frameT + r), Offset(frame.right, frameT + r + cornerLen), cornerPaint);
    // Bottom-left
    canvas.drawLine(Offset(frameL + r, frame.bottom), Offset(frameL + r + cornerLen, frame.bottom), cornerPaint);
    canvas.drawLine(Offset(frameL, frame.bottom - r - cornerLen), Offset(frameL, frame.bottom - r), cornerPaint);
    // Bottom-right
    canvas.drawLine(Offset(frame.right - r - cornerLen, frame.bottom), Offset(frame.right - r, frame.bottom), cornerPaint);
    canvas.drawLine(Offset(frame.right, frame.bottom - r - cornerLen), Offset(frame.right, frame.bottom - r), cornerPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
