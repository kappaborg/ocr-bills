import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

class ConfidenceIndicator extends StatelessWidget {
  final double score;
  const ConfidenceIndicator(this.score, {super.key});

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.confidenceColor(score);
    return Tooltip(
      message: 'Confidence: ${(score * 100).toStringAsFixed(0)}%',
      child: Container(
        width: 10,
        height: 10,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
    );
  }
}
