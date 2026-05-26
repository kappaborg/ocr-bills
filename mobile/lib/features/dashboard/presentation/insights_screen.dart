import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/widgets/error_view.dart';
import '../providers/dashboard_provider.dart';

class InsightsScreen extends ConsumerWidget {
  const InsightsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final insightsAsync = ref.watch(insightsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Insights')),
      body: insightsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorView(message: e.toString(), onRetry: () => ref.invalidate(insightsProvider)),
        data: (insights) {
          if (insights.isEmpty) return const Center(child: Text('No insights available yet.'));
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: insights.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (_, i) {
              final item = insights[i];
              final isSpike = item.type == 'spending_spike';
              final isFreq = item.type == 'frequency_spike';
              return Card(
                child: ListTile(
                  leading: Icon(
                    isSpike ? Icons.trending_up : isFreq ? Icons.repeat : Icons.info_outline,
                    color: isSpike ? Colors.red : isFreq ? Colors.orange : Colors.blue,
                    size: 32,
                  ),
                  title: Text(item.message),
                  subtitle: Text(
                    isSpike ? 'Spending spike' : isFreq ? 'Frequency spike' : 'Info',
                    style: const TextStyle(fontSize: 11),
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
