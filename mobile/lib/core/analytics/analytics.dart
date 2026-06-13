import 'package:flutter/foundation.dart';
import 'package:posthog_flutter/posthog_flutter.dart';

/// Thin wrapper around PostHog. All calls no-op when no API key is set at
/// build time, so dev builds, CI, and tests don't pollute the beta dataset.
/// Pass the key with --dart-define=POSTHOG_API_KEY=phc_...
class Analytics {
  static const _key = String.fromEnvironment('POSTHOG_API_KEY');
  static const _host = String.fromEnvironment(
    'POSTHOG_HOST',
    defaultValue: 'https://eu.i.posthog.com',
  );

  static bool get enabled => _key.isNotEmpty;

  /// Initialize PostHog. Safe to call once on app start; no-op when no key.
  /// Called from main() before runApp.
  static Future<void> init() async {
    if (!enabled) return;
    try {
      final config = PostHogConfig(_key)
        ..host = _host
        ..captureApplicationLifecycleEvents = true
        ..debug = kDebugMode
        // Session replay is the gold for beta observation — see what users
        // actually tap. Sample 100% during the 10-friend beta; tune down later.
        ..sessionReplay = true
        ..sessionReplayConfig.maskAllTexts = false
        ..sessionReplayConfig.maskAllImages = false;
      await Posthog().setup(config);
    } catch (e) {
      // Never let analytics setup break the app.
      debugPrint('Analytics init failed: $e');
    }
  }

  /// Attach the current user to their session so events are attributable.
  static Future<void> identify(int userId, {String? email}) async {
    if (!enabled) return;
    try {
      await Posthog().identify(
        userId: userId.toString(),
        userProperties: {if (email != null) 'email': email},
      );
    } catch (_) {}
  }

  /// Drop the identifier on logout — events after this are anonymous.
  static Future<void> reset() async {
    if (!enabled) return;
    try {
      await Posthog().reset();
    } catch (_) {}
  }

  /// Capture a custom event. Properties are PostHog-flattened on the wire.
  static Future<void> capture(String event, [Map<String, Object>? props]) async {
    if (!enabled) return;
    try {
      await Posthog().capture(eventName: event, properties: props);
    } catch (_) {}
  }
}
