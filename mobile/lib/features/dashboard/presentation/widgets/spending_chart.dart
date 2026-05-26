import 'package:flutter/material.dart';

class SpendingChart extends StatelessWidget {
  final Map<String, double> data;
  const SpendingChart({super.key, required this.data});

  @override
  Widget build(BuildContext context) {
    if (data.isEmpty) {
      return const Center(child: Text('No spending data yet'));
    }

    final sorted = data.entries.toList()..sort((a, b) => b.value.compareTo(a.value));
    final maxVal = sorted.first.value;
    final colors = [
      Colors.blue, Colors.green, Colors.orange, Colors.purple,
      Colors.red, Colors.teal, Colors.amber, Colors.indigo,
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (int i = 0; i < sorted.length && i < 8; i++) ...[
          Row(
            children: [
              SizedBox(
                width: 100,
                child: Text(sorted[i].key, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12)),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: LinearProgressIndicator(
                  value: sorted[i].value / maxVal,
                  color: colors[i % colors.length],
                  backgroundColor: colors[i % colors.length].withValues(alpha: 0.15),
                  minHeight: 18,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              const SizedBox(width: 8),
              Text(sorted[i].value.toStringAsFixed(2), style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 8),
        ],
      ],
    );
  }
}
