import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/preferences/display_currency_provider.dart';
import '../../../core/theme/theme_provider.dart';
import '../../auth/data/auth_repository.dart';
import '../../auth/providers/auth_provider.dart';
import '../../receipts/data/receipts_repository.dart';
import '../../receipts/providers/receipts_provider.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _currentPassCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();
  bool _loading = false;

  @override
  void dispose() {
    _currentPassCtrl.dispose();
    _passCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _changePassword() async {
    if (_currentPassCtrl.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Enter your current password')));
      return;
    }
    if (_passCtrl.text.length < 8) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('New password must be at least 8 characters')));
      return;
    }
    if (_passCtrl.text != _confirmCtrl.text) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Passwords do not match')));
      return;
    }
    setState(() => _loading = true);
    try {
      await ref.read(authProvider.notifier).changePassword(_currentPassCtrl.text, _passCtrl.text);
      _currentPassCtrl.clear();
      _passCtrl.clear();
      _confirmCtrl.clear();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Password updated')));
    } on AppException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message), backgroundColor: Colors.red));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _logout() async {
    await ref.read(authProvider.notifier).logout();
  }

  Future<void> _seedSamples() async {
    setState(() => _loading = true);
    try {
      final res = await ref.read(receiptsRepositoryProvider).seedSampleReceipts();
      if (!mounted) return;
      final already = res['already_loaded'] == true;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(already
            ? 'Sample receipts already present'
            : 'Added ${res['created'] ?? "sample"} receipts — check the dashboard'),
      ));
      ref.read(receiptsListProvider.notifier).load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'), backgroundColor: Colors.red));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _exportData() async {
    setState(() => _loading = true);
    try {
      final json = await ref.read(authRepositoryProvider).exportMyData();
      // Write to a temp file then hand off to the platform share sheet so
      // the user can save to Drive / email it / etc.
      final dir = await getTemporaryDirectory();
      final ts = DateTime.now().toIso8601String().replaceAll(':', '-').split('.').first;
      final file = File('${dir.path}/extasy-export-$ts.json');
      await file.writeAsString(json);
      await Share.shareXFiles([XFile(file.path)], text: 'ExTaSy data export');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Export failed: $e'), backgroundColor: Colors.red));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _deleteAccount() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete account?'),
        content: const Text(
          'This permanently removes your account, receipts, and inventory. '
          'There is no undo. Continue?',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete forever', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _loading = true);
    try {
      await ref.read(authRepositoryProvider).deleteAccount();
      if (!mounted) return;
      // deleteAccount() already cleared the token; trip auth state so the
      // router sends us back to /login.
      await ref.read(authProvider.notifier).logout();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Delete failed: $e'), backgroundColor: Colors.red));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).valueOrNull;
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (user != null)
            ListTile(
              leading: const CircleAvatar(child: Icon(Icons.person)),
              title: Text(user.email),
              subtitle: const Text('Signed in'),
            ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.download_outlined),
            title: const Text('Export CSV'),
            onTap: () => context.push('/export'),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.workspace_premium_outlined),
            title: const Text('Plans & Pricing'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push('/pricing'),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.auto_awesome_outlined),
            title: const Text('Add sample receipts'),
            subtitle: const Text('7 demo receipts so the dashboard isn\'t empty'),
            onTap: _loading ? null : _seedSamples,
          ),
          const Divider(),
          _CurrencyTile(),
          const Divider(),
          _ThemeTile(),
          const Divider(),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text('Change Password', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold)),
          ),
          TextFormField(
            controller: _currentPassCtrl,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'Current Password', prefixIcon: Icon(Icons.lock_outlined)),
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _passCtrl,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'New Password', prefixIcon: Icon(Icons.lock_outlined)),
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _confirmCtrl,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'Confirm Password', prefixIcon: Icon(Icons.lock_outlined)),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _loading ? null : _changePassword,
            child: _loading ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Text('Update Password'),
          ),
          const Divider(height: 32),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text('Your data', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold)),
          ),
          ListTile(
            leading: const Icon(Icons.archive_outlined),
            title: const Text('Download my data'),
            subtitle: const Text('Export receipts, items, products as JSON'),
            onTap: _loading ? null : _exportData,
          ),
          ListTile(
            leading: const Icon(Icons.delete_forever_outlined, color: Colors.red),
            title: const Text('Delete account', style: TextStyle(color: Colors.red)),
            subtitle: const Text('Permanently remove everything'),
            onTap: _loading ? null : _deleteAccount,
          ),
          const Divider(height: 32),
          ListTile(
            leading: const Icon(Icons.logout, color: Colors.red),
            title: const Text('Sign Out', style: TextStyle(color: Colors.red)),
            onTap: _logout,
          ),
        ],
      ),
    );
  }
}

class _CurrencyTile extends ConsumerWidget {
  static const _currencies = ['BAM', 'EUR', 'USD', 'GBP', 'TRY', 'RUB'];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final current = ref.watch(displayCurrencyProvider);
    return ListTile(
      leading: const Icon(Icons.attach_money_outlined),
      title: const Text('Display currency'),
      subtitle: const Text('Used for dashboard totals'),
      trailing: DropdownButton<String>(
        value: _currencies.contains(current) ? current : _currencies.first,
        underline: const SizedBox.shrink(),
        items: _currencies
            .map((c) => DropdownMenuItem(value: c, child: Text(c)))
            .toList(),
        onChanged: (v) {
          if (v != null) ref.read(displayCurrencyProvider.notifier).set(v);
        },
      ),
    );
  }
}

class _ThemeTile extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mode = ref.watch(themeModeProvider);
    return ListTile(
      leading: Icon(switch (mode) {
        ThemeMode.light  => Icons.light_mode_outlined,
        ThemeMode.dark   => Icons.dark_mode_outlined,
        ThemeMode.system => Icons.brightness_auto_outlined,
      }),
      title: const Text('Theme'),
      subtitle: Text(switch (mode) {
        ThemeMode.light  => 'Light',
        ThemeMode.dark   => 'Dark',
        ThemeMode.system => 'Match system',
      }),
      trailing: SegmentedButton<ThemeMode>(
        showSelectedIcon: false,
        style: const ButtonStyle(visualDensity: VisualDensity.compact),
        segments: const [
          ButtonSegment(value: ThemeMode.light,  icon: Icon(Icons.light_mode_outlined, size: 18)),
          ButtonSegment(value: ThemeMode.system, icon: Icon(Icons.brightness_auto_outlined, size: 18)),
          ButtonSegment(value: ThemeMode.dark,   icon: Icon(Icons.dark_mode_outlined, size: 18)),
        ],
        selected: {mode},
        onSelectionChanged: (s) => ref.read(themeModeProvider.notifier).set(s.first),
      ),
    );
  }
}
