import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../../../core/storage/secure_storage.dart';
import '../../dashboard/providers/dashboard_provider.dart';

class ExportScreen extends ConsumerStatefulWidget {
  const ExportScreen({super.key});

  @override
  ConsumerState<ExportScreen> createState() => _ExportScreenState();
}

class _ExportScreenState extends ConsumerState<ExportScreen> {
  DateTime? _from;
  DateTime? _to;
  final Set<String> _selectedCategories = {};
  final _storeCtrl = TextEditingController();
  bool _exporting = false;

  @override
  void dispose() {
    _storeCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickDate(bool isFrom) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: isFrom ? (_from ?? DateTime.now().subtract(const Duration(days: 30))) : (_to ?? DateTime.now()),
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
    );
    if (picked != null) setState(() => isFrom ? _from = picked : _to = picked);
  }

  Future<void> _export() async {
    setState(() => _exporting = true);
    try {
      final token = await SecureStorage.getToken();
      final api = ref.read(apiClientProvider);
      final fmt = DateFormat('yyyy-MM-dd');
      final params = <String, dynamic>{
        if (_from != null) 'date_from': fmt.format(_from!),
        if (_to != null) 'date_to': fmt.format(_to!),
        if (_storeCtrl.text.trim().isNotEmpty) 'store': _storeCtrl.text.trim(),
        if (_selectedCategories.length == 1) 'category': _selectedCategories.first,
      };

      final res = await api.dio.get(
        Endpoints.transactionsExport,
        queryParameters: params,
        options: Options(responseType: ResponseType.bytes, headers: {'Authorization': 'Bearer $token'}),
      );

      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/export_${DateTime.now().millisecondsSinceEpoch}.csv');
      await file.writeAsBytes(res.data as List<int>);

      await Share.shareXFiles([XFile(file.path)], text: 'Receipt transactions export');
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Export failed: $e'), backgroundColor: Colors.red));
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final categoriesAsync = ref.watch(categoriesProvider);
    final fmt = DateFormat('dd MMM yyyy');

    return Scaffold(
      appBar: AppBar(title: const Text('Export CSV')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Date Range', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.calendar_today, size: 16),
                  label: Text(_from == null ? 'From' : fmt.format(_from!)),
                  onPressed: () => _pickDate(true),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.calendar_today, size: 16),
                  label: Text(_to == null ? 'To' : fmt.format(_to!)),
                  onPressed: () => _pickDate(false),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _storeCtrl,
            decoration: const InputDecoration(labelText: 'Store name (optional)', prefixIcon: Icon(Icons.store_outlined)),
          ),
          const SizedBox(height: 16),
          Text('Categories', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          categoriesAsync.when(
            loading: () => const CircularProgressIndicator(),
            error: (_, __) => const Text('Could not load categories'),
            data: (cats) => Wrap(
              spacing: 8,
              children: cats.map((c) => FilterChip(
                label: Text(c),
                selected: _selectedCategories.contains(c),
                onSelected: (v) => setState(() => v ? _selectedCategories.add(c) : _selectedCategories.remove(c)),
              )).toList(),
            ),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _exporting ? null : _export,
            icon: _exporting
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.download),
            label: const Text('Export & Share'),
          ),
        ],
      ),
    );
  }
}
