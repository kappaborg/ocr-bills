import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// Shows the soft-wall dialog when the backend returns HTTP 402 from an
/// upload endpoint (free / pro plan hit its monthly receipt quota).
///
/// Returns true if a dialog was shown (caller can early-return so it doesn't
/// also surface a "Upload failed" snackbar). Returns false if [error] is
/// not a quota error.
Future<bool> handleQuotaError(BuildContext context, Object error) async {
  if (error is! DioException) return false;
  if (error.response?.statusCode != 402) return false;

  final detail = error.response?.data is Map ? error.response!.data as Map : const {};
  final message = detail['detail']?['message'] as String? ??
      detail['message'] as String? ??
      detail['detail'] as String? ??
      'You\'ve reached this period\'s receipt limit.';
  final planRequired = (detail['detail']?['plan_required'] as String?) ?? 'pro';

  await showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Row(children: [
        Icon(Icons.workspace_premium_outlined, color: Colors.amber),
        SizedBox(width: 8),
        Text('Upgrade required'),
      ]),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(message),
          const SizedBox(height: 12),
          Text(
            planRequired == 'business'
                ? 'Business: unlimited receipts, team sharing, accountant exports.'
                : 'Pro: 500 receipts/month, advanced insights, multi-currency.',
            style: const TextStyle(fontSize: 13),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Not now')),
        FilledButton(
          onPressed: () {
            Navigator.pop(ctx);
            context.push('/pricing');
          },
          child: const Text('See plans'),
        ),
      ],
    ),
  );
  return true;
}
