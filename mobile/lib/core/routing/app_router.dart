import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/presentation/register_screen.dart';
import '../../features/auth/providers/auth_provider.dart';
import '../../features/dashboard/presentation/dashboard_screen.dart';
import '../../features/dashboard/presentation/insights_screen.dart';
import '../../features/inventory/presentation/inventory_screen.dart';
import '../../features/receipts/presentation/receipt_confirm_screen.dart';
import '../../features/receipts/presentation/receipt_detail_screen.dart';
import '../../features/receipts/presentation/receipts_list_screen.dart';
import '../../features/scanner/presentation/scanner_screen.dart';
import '../../features/settings/presentation/export_screen.dart';
import '../../features/settings/presentation/settings_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final authListenable = _AuthListenable(ref);

  return GoRouter(
    refreshListenable: authListenable,
    redirect: (context, state) {
      final authState = ref.read(authProvider);
      final isLoading = authState.isLoading;
      final isAuth = authState.valueOrNull != null;
      final loc = state.uri.toString();

      if (isLoading) return '/splash';
      if (!isAuth && loc != '/login' && loc != '/register') return '/login';
      if (isAuth && (loc == '/login' || loc == '/register' || loc == '/splash')) return '/home/dashboard';
      return null;
    },
    routes: [
      GoRoute(path: '/splash', builder: (_, __) => const _SplashScreen()),
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()),
      GoRoute(path: '/insights', builder: (_, __) => const InsightsScreen()),
      GoRoute(path: '/settings', builder: (_, __) => const SettingsScreen()),
      GoRoute(path: '/export', builder: (_, __) => const ExportScreen()),
      GoRoute(
        path: '/receipt/:id',
        builder: (_, state) => ReceiptDetailScreen(receiptId: int.parse(state.pathParameters['id']!)),
        routes: [
          GoRoute(
            path: 'confirm',
            builder: (_, state) => ReceiptConfirmScreen(receiptId: int.parse(state.pathParameters['id']!)),
          ),
        ],
      ),
      StatefulShellRoute.indexedStack(
        builder: (_, __, shell) => _HomeShell(shell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/home/dashboard', builder: (_, __) => const DashboardScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/home/scan', builder: (_, __) => const ScannerScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/home/receipts', builder: (_, __) => const ReceiptsListScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/home/inventory', builder: (_, __) => const InventoryScreen())]),
        ],
      ),
    ],
    initialLocation: '/splash',
  );
});

class _AuthListenable extends ChangeNotifier {
  final Ref _ref;
  _AuthListenable(this._ref) {
    _ref.listen(authProvider, (_, __) => notifyListeners());
  }
}

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
}

class _HomeShell extends StatelessWidget {
  final StatefulNavigationShell shell;
  const _HomeShell({required this.shell});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: shell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: shell.currentIndex,
        onDestinationSelected: (i) => shell.goBranch(i, initialLocation: i == shell.currentIndex),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'Dashboard'),
          NavigationDestination(icon: Icon(Icons.camera_alt_outlined), selectedIcon: Icon(Icons.camera_alt), label: 'Scan'),
          NavigationDestination(icon: Icon(Icons.receipt_long_outlined), selectedIcon: Icon(Icons.receipt_long), label: 'Receipts'),
          NavigationDestination(icon: Icon(Icons.inventory_2_outlined), selectedIcon: Icon(Icons.inventory_2), label: 'Inventory'),
        ],
      ),
    );
  }
}
